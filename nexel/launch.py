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
import uuid

RX_USERNAME = re.compile(r'^[0-9a-zA-Z\-\_\.]+$')
RX_USERCHAR = re.compile(r'^[0-9a-zA-Z\-\_\.]{1}$')
DEFAULT_USERNAME = 'user'
CHARS = string.digits + string.letters
IP_DELAY = datetime.timedelta(seconds=5)
BOOT_DELAY = datetime.timedelta(seconds=10)

parse_email = formencode.validators.Email.to_python


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def random_chars(num_chars):
    return ''.join([random.choice(CHARS) for _ in range(num_chars)])


def email_to_username(email):
    prefix = email.split('@')[0]
    username = ''
    for c in prefix:
        if RX_USERCHAR.match(c) is not None:
            username += c
    if username == '':
        username = DEFAULT_USERNAME
    return username


def generate_id():
    return 'L-%s-%s' % (random_chars(10), uuid.uuid1().hex)


# TODO: add an event to delete all expired launches
class LaunchProcess(object):
    __current_processes = {}

    def __init__(self, acc_name, mach_name, auth_type, auth_value):
        self._acc_name = acc_name # TODO: check acc_name
        self._mach_name = mach_name # TODO: check mach_name
        self._auth_type = auth_type
        self._username = None
        self._email = None
        self._password = None
        self._key_name = Accounts()[acc_name]['auth']['key-name']
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
        return IOLoop().instance()

    @classmethod
    def all_ids(cls):
        return cls.__current_processes.keys()

    @classmethod
    def get(cls, launch_id):
        if not launch_id in cls.__current_processes:
            return None
        return cls.__current_processes[launch_id]

    def launch_id(self):
        return self._launch_id

    def account_name(self):
        return self._acc_name

    def server_id(self):
        return self._server_id

    def ip_address(self):
        return self._ip_address

    def server_ready(self):
        return self._server_ready

    def completed(self):
        if (self._process['keygen'] == 2 and
            self._process['server_add'] == 2 and
            self._process['server_ip'] == 2 and
            self._process['datamount_add'] == 2 and
            self._process['server_ready'] == 2):
            return True
        return False

    def _error(self, code):
        self._error_code = code

    def error_code(self):
        return self._error_code

    def start(self):
        print 'in start()'
        self.io_loop().add_callback(self._continue)

    def _continue(self):
        logger.debug('in _continue()')
        # 1. keygen
        if self._process['keygen'] == 0:
            return self._do_keygen()

        # 2. server_add
        if self._process['server_add'] == 0:
            return self._do_server_add()

        # 3. server_ip
        if self._process['server_ip'] == 0:
            return self._do_server_ip()

        # 4. datamount_add
        if self._process['datamount_add'] == 0:
            return self._do_datamount_add()

        # 5. server_ready
        if self._process['server_ready'] == 0:
            return self._do_server_ready()

        print 'done launch for %s' % self._launch_id

    def _do_keygen(self):
        logger.debug('in _do_keygen')
        self._process['keygen'] = 1

        # check for datamount
        if self._datamount is None:
            self._process['keygen'] = 2
            self._continue()
            return

        # generate keys asynchronously
        def callback(keys):
            self._key_pub, self._key_priv = keys
            self._process['keygen'] = 2
            self._continue()
        generate_key_async(callback)

    def _do_server_add(self):
        logger.debug('in _do_server_add')
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

        # construct cloud-init script
        cloud_init  = '#!/bin/bash\n'
        cloud_init += 'IP_ADDRESS=`curl http://169.254.169.254/2009-04-04/meta-data/local-ipv4`\n'
        cloud_init += 'echo "nexel(%s): start"\n' % self._acc_name
        cloud_init += 'echo "nexel(%s): data=%s"\n' % (self._acc_name, jdata.replace('\"', '\\\"'))

        # provide user access via ssh
        cloud_init += 'useradd -p %s %s\n' % (password_enc, self._username)
        cloud_init += 'sed -i \'s/^PasswordAuthentication.*$/PasswordAuthentication yes/g\' /etc/ssh/sshd_config\n'
        cloud_init += '/etc/init.d/sshd restart\n'

        # correct the hostname
        cloud_init += 'echo "$IP_ADDRESS %s %s.localdomain" >> /etc/hosts\n' % (self._mach_name, self._mach_name)

        # add key and mount sshfs
        # sshfs option: -o ciphers=arcfour
        cloud_init += 'mkdir -p ~/.ssh\n'
        cloud_init += 'echo "%s" > ~/.ssh/id_rsa\n' % self._key_priv
        cloud_init += 'chmod 600 ~/.ssh/id_rsa\n'
        cloud_init += 'mkdir /mnt/data\n'
        # TODO: put into Datamount() configuration
        sshfs_cmd = '/usr/local/bin/sshfs'
        sshfs_domain = Datamounts()[self._datamount]['server']['domain']
        if self._auth_type == 'username':
            cloud_init += '%s -o StrictHostKeyChecking=no -o allow_other %s@%s: /mnt/data\n' % (sshfs_cmd, self._username, sshfs_domain)
        else:
            cloud_init += '%s -o StrictHostKeyChecking=no -o allow_other "%s"@%s: /mnt/data\n' % (sshfs_cmd, self._email, sshfs_domain)

        # add custom boot-up script to cloud_init (eg. update an app, put a shortcut on the desktop)
        # as provided in Accounts()

        # setup a monitor and kill script

        # overwrite the standard NoMachine key files
        privNoMachineKeyFile = open(Settings()['nx_key_path']+"/nxprivate.key", "r")
        privNoMachineKey = privNoMachineKeyFile.read()
        privNoMachineKeyFile.close()
        privNoMachineKey += 'EOF\n'
        cloud_init += 'cat > /usr/NX/share/keys/default.id_dsa.key << EOF\n'
        cloud_init += privNoMachineKey

        pubNoMachineKeyFile = open(Settings()['nx_key_path']+"/nxpublic.key", "r")
        pubNoMachineKey = pubNoMachineKeyFile.read()
        pubNoMachineKeyFile.close()
        pubNoMachineKey += 'EOF\n'
        cloud_init += 'cat > /usr/NX/home/nx/.ssh/default.id_dsa.pub << EOF\n'
        cloud_init += pubNoMachineKey
        cloud_init += 'cp /usr/NX/home/nx/.ssh/default.id_dsa.pub /usr/NX/home/nx/.ssh/authorized_keys2'

        # write to meta-data: nexel-ready=True
        auth = Accounts()[self._acc_name]['auth']
        #cloud_init += 'echo "#!/usr/bin/env python\n'
        cloud_init += 'echo "import urllib2 # adapt for python 3+\n' #TODO
        cloud_init += 'import json\n'
        cloud_init += '\n'
        cloud_init += 'tenant_id = \'%s\'\n' % auth['tenant_id']
        cloud_init += 'username = \'%s\'\n' % auth['username']
        cloud_init += 'password = \'%s\'\n' % auth['password']
        cloud_init += 'auth_url = \'%s\'\n' % Settings()['os_auth_url']
        cloud_init += 'nova_url = \'%s\'\n' % Settings()['os_nova_url']
        cloud_init += '\n'
        cloud_init += 'headers = {\'Content-Type\': \'application/json\'}\n'
        cloud_init += 'body = {\'auth\' :{\'passwordCredentials\': {\'username\': username, \'password\': password}, \'tenantId\': tenant_id}}\n'
        cloud_init += 'url = auth_url+\'/tokens\'\n'
        cloud_init += 'req = urllib2.Request(url, headers=headers, data=json.dumps(body))\n'
        cloud_init += 'resp = urllib2.urlopen(req)\n'
        cloud_init += 'j = json.loads(resp.read())\n'
        cloud_init += 'token = j[\'access\'][\'token\'][\'id\']\n'
        cloud_init += '\n'
        cloud_init += 'url = \'http://169.254.169.254/openstack/2012-08-10/meta_data.json\'\n'
        cloud_init += 'req = urllib2.Request(url)\n'
        cloud_init += 'resp = urllib2.urlopen(req)\n'
        cloud_init += 'j = json.loads(resp.read())\n'
        cloud_init += 'server_id = j[\'uuid\']\n'
        cloud_init += '\n'
        cloud_init += 'headers[\'X-Auth-Token\'] = token\n'
        cloud_init += 'body = {\'metadata\': {\'nexel-ready\': \'True\'}}\n'
        cloud_init += 'url = nova_url+\'/\'+tenant_id+\'/servers/\'+server_id+\'/metadata\'\n'
        cloud_init += 'req = urllib2.Request(url, headers=headers, data=json.dumps(body))\n'
        cloud_init += 'resp = urllib2.urlopen(req)\n'
        cloud_init += '" > ~/nexel-ready.py\n'

        # finish script
        cloud_init += 'echo "nexel(%s): end"\n' % self._acc_name
        cloud_init += 'python ~/nexel-ready.py\n'
        cloud_init += 'rm -rf ~/nexel-ready.py\n'

        # boot the server, get srv_id
        mach = Accounts()[self._acc_name]['machines'][self._mach_name]['boot']
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
        # logger.debug(cloud_init)

        def callback(resp):
            try:
                logger.debug(resp.body)
                if resp.code == 413:
                    logger.error('error quota exceeded 413')
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
            self._continue()
        req = OpenStackRequest(self._acc_name, 'POST', '/servers', body=body)
        make_request_async(req, callback)

    def _do_server_ip_op(self):
        logger.debug('in _do_server_ip_op')

        def callback(resp):
            try:
                j = json.loads(resp.body)
                addr = j['server']['addresses']
                self._ip_address = addr[addr.keys()[0]][0]['addr']
                self._process['server_ip'] = 2
                logger.debug('got ip %s' % self._ip_address)
            except Exception, e:
                logger.debug('havent got ip address')
                # logger.exception(e)
                self.io_loop().add_timeout(IP_DELAY, self._do_server_ip_op)
                # TODO: have a maximum termination (time-out)
            if self._process['server_ip'] == 2:
                self._continue()
        req = OpenStackRequest(self._acc_name,
                               'GET', '/servers/' + self._server_id)
        make_request_async(req, callback)

    def _do_server_ip(self):
        logger.debug('in _do_server_ip')
        self._process['server_ip'] = 1
        self.io_loop().add_timeout(IP_DELAY, self._do_server_ip_op)

    def _do_datamount_add(self):
        logger.debug('in _do_datamount_add')
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

        # generate keys asynchronously
        def callback(result):
            # result = True/False
            self._process['datamount_add'] = 2
            self._continue()
        if self._auth_type == 'username':
            add_key_to_data_server_async(callback, self._datamount, ssh_key, username=self._username)
        else:
            add_key_to_data_server_async(callback, self._datamount, ssh_key, username=self._email)

    def _do_server_ready_op(self):
        logger.debug('in _do_server_ready_op')

        def callback(resp):
            try:
                j = json.loads(resp.body)
                if j['meta']['nexel-ready'].lower() == 'true':
                    self._server_ready = True
                    self._process['server_ready'] = 2
                    logger.debug('server is ready')
            except Exception, e:
                logger.exception(e)
                pass
            if self._process['server_ready'] == 2:
                self._continue()
                return
            self.io_loop().add_timeout(BOOT_DELAY, self._do_server_ready_op)
        req = OpenStackRequest(self._acc_name, 'GET', '/servers/'+self._server_id+'/metadata/nexel-ready')
        make_request_async(req, callback)

    def _do_server_ready(self):
        logger.debug('in _do_server_ready')
        self._process['server_ready'] = 1
        self.io_loop().add_timeout(BOOT_DELAY, self._do_server_ready_op)
