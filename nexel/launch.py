#------------------------------------------------------------
#                            NEXEL
#
#   Performs the asynchronous launch of a Nectar Instance
#
#------------------------------------------------------------

import base64
import crypt
from Crypto.Random import random
import datetime
import formencode.validators
import json
import logging
from nexel.config.accounts import Accounts
from nexel.config.datamounts import Datamounts
from nexel.config.settings import Settings
import re
import string
from tornado.ioloop import IOLoop
from tornado.web import HTTPError
from nexel.util.openstack import OpenStackRequest, make_request_async
from nexel.util.ssh import generate_key_async, add_key_to_data_server_async
from jinja2 import Environment, FileSystemLoader
import uuid
import os
import time


# global constants for this script
RX_USERNAME = re.compile(r'^[0-9a-zA-Z\-\_\.]+$')
RX_USERCHAR = re.compile(r'^[0-9a-zA-Z\-\_\.]{1}$')
DEFAULT_USERNAME = 'user'
CHARS = string.digits + string.letters
IP_DELAY = datetime.timedelta(seconds=int(Settings()['server_ip_refresh']))
BOOT_DELAY = datetime.timedelta(seconds=int(Settings()['server_ready_refresh']))

parse_email = formencode.validators.Email.to_python


# the logging system
logger = logging.getLogger(__name__)


#-------------------------------------
#          Global methods
#-------------------------------------
def random_chars(num_chars):
    """
    Returns a string consisting of random characters.
    num_chars : The number of random characters.
    """
    return ''.join([random.choice(CHARS) for _ in range(num_chars)])


def email_to_username(email):
    """
    Converts and returns an email address to a username by stripping off all characters behind @.
    Checks if the username is alphanumeric. If not, the default username is returned.
    email : The email address which should be converted to a username.
    """
    prefix = email.split('@')[0]
    username = ''
    for c in prefix:
        if RX_USERCHAR.match(c) is not None:
            username += c
    if username == '':
        username = DEFAULT_USERNAME
    return username


def generate_id():
    """
    Generates and returns a launch ID starting with "L" from random characters and a unique ID.
    """
    return 'L-%s-%s' % (random_chars(10), uuid.uuid1().hex)


#-------------------------------------
#         LaunchProcess class
#-------------------------------------
# TODO: add an event to delete all expired launches
class LaunchProcess(object):
    """
    The main launch process class.
    """

    __current_processes = {}

    def __init__(self, acc_name, mach_name, auth_type, auth_value, cell_hint="", extra={}):
        """
        The constructor of the launch process class.
        acc_name   : The name of the Nexel user account that launches the VM.
        mach_name  : The name of the Nexel machine that should be launched.
        auth_type  : The type of the authentication. Either "username" or "email".
        auth_value : Depending on the authentication type, this holds either
                     the username or the email value.
        cell_hint  : [optional] forces the use of a specific cloud cell. If none is given,
                     the cell_hint from the settings file is used.
        extra      : [optional] additional information that can be accessed in
                     the cloud init script template.
        """
        # check if the account and machine names exist
        if acc_name not in Accounts():
            logger.error('Cannot launch the instance: The account "'+acc_name+'" does not exist!')
            raise HTTPError(400)

        if mach_name not in Accounts()[acc_name]['machines']:
            logger.error('Cannot launch the instance: The machine "'+mach_name+'" does not exist!')
            raise HTTPError(400)

        # prepare the launch process and add it to the list of current processes
        self._acc_name = acc_name
        self._mach_name = mach_name
        self._auth_type = auth_type
        self._username = None
        self._email = None
        self._password = None
        self._key_name = Accounts()[acc_name]['auth']['key-name']
        if cell_hint:
            self._cell_hint = cell_hint
        else:
            self._cell_hint = Accounts()[acc_name]['machines'][mach_name]['boot']['cell_hint']
        self._extra_template_values = extra
        try:
            assert(auth_value != '')
            if self._auth_type == 'username':
                assert(RX_USERNAME.match(auth_value) is not None)
                self._username = auth_value
                self._email = None
            elif self._auth_type == 'email':
                self._email = parse_email(auth_value)
                self._username = email_to_username(auth_value)
            else:
                raise HTTPError(400)
        except Exception, e:
            logger.exception(e)
            raise HTTPError(400)
        self._cancel_launch = False
        self._launch_timeout_handle = None
        self._launch_id = generate_id()
        self._created = datetime.datetime.now()
        self._key_pub = None
        self._key_priv = None
        self._server_id = None
        self._datamount = Accounts()[acc_name]['machines'][mach_name]['boot']['datamount']
        self._process = {'keygen': 0,
                         'server_add': 0,
                         'server_ip': 0,
                         'datamount_add': 0,
                         'server_ready': 0}
        self._error_code = None
        self._ip_address = None
        self._server_ready = False
        self.__current_processes[self._launch_id] = self
        print self.__current_processes


    @classmethod
    def io_loop(cls):
        """Returns the instance of the Tornado IOLoop singleton."""
        return IOLoop().instance()

    @classmethod
    def all_ids(cls):
        """Returns a list of all launch IDs."""
        return cls.__current_processes.keys()

    @classmethod
    def get(cls, launch_id):
        """
        Returns a list of all launch processes if the specified launch ID doesn't exist.
        Otherwise returns the launch process of the given launch ID.
        launch_id : The launch ID
        """
        if not launch_id in cls.__current_processes:
            return None
        return cls.__current_processes[launch_id]


    def launch_id(self):
        """Returns the ID of this launch process."""
        return self._launch_id

    def account_name(self):
        """Returns the account name that was used to create this launch process."""
        return self._acc_name

    def server_id(self):
        """Returns the unique ID of the launched instance."""
        return self._server_id

    def ip_address(self):
        """Returns the IP address of the launched instance."""
        return self._ip_address

    def server_ready(self):
        """Returns True if the instance is running. Otherwise returns False."""
        return self._server_ready

    def completed(self):
        """Returns True if the instance has been launched successfully. Otherwise returns False."""
        if (self._process['keygen'] == 2 and
            self._process['server_add'] == 2 and
            self._process['server_ip'] == 2 and
            self._process['datamount_add'] == 2 and
            self._process['server_ready'] == 2):
            return True
        return False

    def _error(self, code):
        """
        Sets the error code of this launch process to the specified code.
        code : The error code that should be set.
        """
        self._error_code = code

    def error_code(self):
        """Returns the current error code of this launch process."""
        return self._error_code


    def status(self):
        """
        Returns the current launch status as an integer value.
        Values greater than 0 indicate a lunch status.
        The value -1 indicates that the launch process timed out.
        """
        if self._cancel_launch:
            return -1

        statusSum = 0
        for key, value in self._process.iteritems():
            statusSum += value
        return statusSum/2
        

    def start(self):
        """Starts the launch process by:
            - adding the _timeout() method to  Tornado's IO loop
            - adding the _continue() method to Tornado's IO loop
        """
        logger.debug('Adding the _timeout() and _continue() methods to Tornado\'s IO loop')
        logger.info('Launching instance <%s> for user <%s>, account <%s> and machine <%s>' \
                    %(self._launch_id, self._username, self._acc_name, self._mach_name))
        self._launch_timeout_handle = self.io_loop().add_timeout(datetime.timedelta(seconds=int(Settings()['launch_timeout'])), self._timeout)
        self.io_loop().add_callback(self._continue)


    def _timeout(self):
        """
        This method is called when the launch process exceeds the specified time threshold.
        It stops the launch and terminates the instance.
        """
        logger.error('Timeout of the launch process <%s> reached. Stopping the process.'%self._launch_id)
        self._cancel_launch = True

        def callback(resp):
            logger.debug('Terminated the instance.')

        if self._server_id != None:
            req = OpenStackRequest(self._acc_name, 'DELETE', '/servers/'+self._server_id)
            make_request_async(req, callback)



    def _continue(self):
        """This method calls all steps involved in launching an instance."""

        # 1. generate the public and private key for mounting the data
        if self._process['keygen'] == 0:
            return self._do_keygen()

        # 2. launches the instance on the Nectar cloud
        if (not self._cancel_launch) and (self._process['server_add'] == 0):
            return self._do_server_add()

        # 3. retrieves the instance's IP address
        if (not self._cancel_launch) and (self._process['server_ip'] == 0):
            return self._do_server_ip()

        # 4. adds the public key to the data server
        if (not self._cancel_launch) and (self._process['datamount_add'] == 0):
            return self._do_datamount_add()

        # 5. sets the instance's server_ready flag to "true"
        if (not self._cancel_launch) and (self._process['server_ready'] == 0):
            return self._do_server_ready()

        if self._cancel_launch:
            return

        # Stop the timeout countdown
        self.io_loop().remove_timeout(self._launch_timeout_handle)

        logger.info('Done launch of instance <%s> for user <%s>, account <%s> and machine <%s>' \
                    %(self._launch_id, self._username, self._acc_name, self._mach_name))


    def _do_keygen(self):
        """Generate the public and private key for mounting the data"""
        logger.debug('(1) Generating the key pair...')
        self._process['keygen'] = 1

        # check for datamount
        if self._datamount is None:
            self._process['keygen'] = 2
            self._continue()
            return

        # generate keys asynchronously
        def callback(keys):
            """
            Callback method for the asynchronous generation of the key pair
            keys : the generated private and public keys
            """
            self._key_pub, self._key_priv = keys
            self._process['keygen'] = 2
            logger.debug('(1) ...key pair generation successful')
            self._continue()
        generate_key_async(callback)


    def _do_server_add(self):
        """Launches the instance on the Nectar cloud"""
        logger.debug('(2) Launching the instance on the Nectar cloud...')
        self._process['server_add'] = 1

        # generate a random password for the session, encrypt for linux
        self._password = random_chars(20)
        password_enc = crypt.crypt(self._password, 'password')

        # define nexel id and echo data
        echo_data = {'launch_id': self._launch_id,
                     'ip_address': '$IP_ADDRESS',
                     'acc_name': self._acc_name,
                     'mach_name': self._mach_name,
                     'auth_type': self._auth_type,
                     'username': self._username,
                     'email': self._email,
                     'password': self._password}
        jdata = json.dumps(echo_data, separators=(',', ':'))

        # set the sshfs datamount settings
        sshfsUser = ""
        if self._auth_type == 'username':
            sshfsUser = self._username
        else:
            sshfsUser = '"%s"' % self._email
        if self._datamount is None:
            sshfs_domain = ""
        else:
            sshfs_domain = Datamounts()[self._datamount]['server']['domain']

        # get Nexel authentication and machine data
        auth = Accounts()[self._acc_name]['auth']
        mach = Accounts()[self._acc_name]['machines'][self._mach_name]['boot']

        # construct cloud-init script from template
        cloud_init_env = Environment(loader=FileSystemLoader(
                          os.path.join(Settings()['accounts_path'], self._acc_name,
                                       'machines', self._mach_name)))
        cloud_init_template = cloud_init_env.get_template(mach['cloud_init'])
        cloud_init_vars = {
                            'accountName'      : self._acc_name,
                            'echoData'         : jdata.replace('\"', '\\\"'),
                            'passwordEnc'      : password_enc,
                            'username'         : self._username,
                            'password'         : self._password,
                            'machineName'      : self._mach_name,
                            'keyPrivate'       : self._key_priv,
                            'sshfsUser'        : sshfsUser,
                            'sshfsDomain'      : sshfs_domain,
                            'tenantId'         : auth['tenant_id'],
                            'nectarUsername'   : auth['username'],
                            'nectarPassword'   : auth['password'],
                            'osAuthURL'        : Settings()['os_auth_url'],
                            'osNovaURL'        : Settings()['os_nova_url'],
                            'initShutdown'     : str(int(Settings()['init_shutdown'])/60),
                            'nxLogoutShutdown' : str(int(Settings()['nx_logout_shutdown'])/60)
                          }
        cloud_init_vars.update(self._extra_template_values)
        cloud_init = cloud_init_template.render(cloud_init_vars)

        # boot the server, get srv_id
        body = {'server': {'name': self._mach_name,
                           'imageRef': mach['snapshot_id'],
                           'flavorRef': mach['flavor_id'],
                           'security_groups': [{'name': 'ssh'}],
                           'user_data': base64.b64encode(cloud_init),
                           'metadata': {'nexel-type': 'instance',
                                        'nexel-ready': 'False',
                                        'nexel-username': self._username,
                                        'nexel-password': self._password},
                           'key_name': self._key_name, }}
        if self._cell_hint:
            body['os:scheduler_hints'] = {'cell': self._cell_hint}


        def callback(resp):
            """
            Callback method for the asynchronous launch request to the Nectar cloud
            resp : the response of the Nectar cloud
            """
            try:
                logger.debug(resp.body)
                if resp.code == 413:
                    logger.error('Exceeded the quota of concurrently running instances at the Nectar cloud!')
                    self._error(413)
                    return
                j = json.loads(resp.body)
                server_id = j['server']['id']
                assert(server_id != '')
            except Exception, e:
                logger.exception(e)
                self._error(500)
                return
            self._server_id = server_id
            self._process['server_add'] = 2
            logger.debug('(2) ...launch of the instance successful (%s)' % self._server_id)
            self._continue()
        req = OpenStackRequest(self._acc_name, 'POST', '/servers', body=body)
        make_request_async(req, callback)


    def _do_server_ip_op(self):
        """Retrieves the instance's IP address"""

        def callback(resp):
            """
            Callback method for the asynchronous retrieval of the IP address
            resp : the response of the Nectar cloud
            """
            try:
                j = json.loads(resp.body)
                addr = j['server']['addresses']
                self._ip_address = addr[addr.keys()[0]][0]['addr']
                self._process['server_ip'] = 2
            except Exception, e:
                if not self._cancel_launch:
                    logger.debug('...waiting...')
                    self.io_loop().add_timeout(IP_DELAY, self._do_server_ip_op)
            if self._process['server_ip'] == 2:
                logger.debug('(3) ...got the IP address (%s)' % self._ip_address)
                self._continue()
        req = OpenStackRequest(self._acc_name, 'GET', '/servers/' + self._server_id)
        make_request_async(req, callback)

    def _do_server_ip(self):
        """Adds the IP address retrieval method to Tornado's IO loop with a delay"""
        logger.debug('(3) Retrieving the IP address of the instance...')
        self._process['server_ip'] = 1
        self.io_loop().add_timeout(IP_DELAY, self._do_server_ip_op)


    def _do_datamount_add(self):
        """Adds the public key to the data server"""
        logger.debug('(4) Adding the public key to the data server...')
        self._process['datamount_add'] = 1

        # check for datamount
        if self._datamount is None:
            self._process['datamount_add'] = 2
            self._continue()
            return

        # add ip address to ssh key
        #ip_protect = 'from="%s",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty' % self._ip_address
        ip_protect = 'from="%s"' % self._ip_address
        comment = '(Generated by Nexel on %s)' % datetime.datetime.now().isoformat()
        ssh_key = '%s %s %s' % (ip_protect, self._key_pub, comment)

        def callback(result):
            """
            Callback method for the asynchronous adding of the public key to the data server
            result : the result as a Boolean value
            """
            self._process['datamount_add'] = 2
            logger.debug('(4) ...key has been added successfully')
            self._continue()
        if self._auth_type == 'username':
            add_key_to_data_server_async(callback, self._datamount, ssh_key, username=self._username)
        else:
            add_key_to_data_server_async(callback, self._datamount, ssh_key, username=self._email)


    def _do_server_ready_op(self):
        """Checks if the nexel-ready flag is true. If it is, the instance has finished booting"""

        def callback(resp):
            """
            Callback method to set the server_ready flag asynchronously
            resp : the response of the Nectar cloud
            """
            try:
                j = json.loads(resp.body)
                if j['meta']['nexel-ready'].lower() == 'true':
                    self._server_ready = True
                    self._process['server_ready'] = 2
            except Exception, e:
                logger.exception(e)
                pass
            if self._process['server_ready'] == 2:
                logger.debug('(5) ...done. Set the server_ready flag to true.')
                self._continue()
                return
            if not self._cancel_launch:
                self.io_loop().add_timeout(BOOT_DELAY, self._do_server_ready_op)
        req = OpenStackRequest(self._acc_name, 'GET', '/servers/'+self._server_id+'/metadata/nexel-ready')
        make_request_async(req, callback)

    def _do_server_ready(self):
        """Adds the method to set the server_ready flat to Tornado's IO loop with a delay"""
        logger.debug('(5) Waiting for the launch of the instance to complete...')
        self._process['server_ready'] = 1
        self.io_loop().add_timeout(BOOT_DELAY, self._do_server_ready_op)
