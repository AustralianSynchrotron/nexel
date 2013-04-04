import base64
from Crypto.Random import random
import datetime
import json
import logging
from nexel.config.accounts import Accounts
from nexel.config.settings import Settings
import string
from tornado.ioloop import IOLoop
from nexel.util.openstack\
import OpenStackRequest, make_request_async, http_success
import uuid
import urllib

CHARS = string.digits + string.letters
BUILD_DELAY = datetime.timedelta(seconds=30)
SNAPSHOT_DELAY = datetime.timedelta(seconds=30)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def random_chars(num_chars):
    return ''.join([random.choice(CHARS) for _ in range(num_chars)])


def generate_id():
    return 'S-%s-%s' % (random_chars(10), uuid.uuid1().hex)


class SnapshotProcess(object):
    __current_processes = {}

    def __init__(self, acc_name, mach_name):
        self._mach_name = mach_name
        self._auth = Accounts()[acc_name]['auth']
        self._settings = Accounts()[acc_name]['machines'][mach_name]['build']
        self._acc_name = acc_name
        self._snapshot_id = generate_id()
        self._created = datetime.datetime.now()
        self._acc_name = acc_name
        self._server_id = None
        self._process = {'server_add': 0,
                         'server_ready': 0,
                         'snapshot_create': 0,
                         'snapshot_ready': 0,
                         'snapshot_save': 0,
                         'server_kill': 0}
        self._error_code = None
        self._ip_address = None
        self._server_ready = False
        self._snapshot_name = None
        self._os_snapshot_id = None
        self.__current_processes[self._snapshot_id] = self

    @classmethod
    def io_loop(cls):
        return IOLoop().instance()

    @classmethod
    def all_ids(cls):
        return cls.__current_processes.keys()

    @classmethod
    def get(cls, snapshot_id):
        if not snapshot_id in cls.__current_processes:
            return None
        return cls.__current_processes[snapshot_id]

    def snapshot_id(self):
        return self._snapshot_id

    def account_name(self):
        return self._acc_name

    def server_id(self):
        return self._server_id

    def ip_address(self):
        return self._ip_address

    def server_ready(self):
        return self._server_ready

    def completed(self):
        if (self._process['server_add'] == 2 and
            self._process['server_ready'] == 2 and
            self._process['snapshot_create'] == 2 and
            self._process['snapshot_ready'] == 2 and
            self._process['snapshot_save'] == 2 and
            self._process['server_kill'] == 2):
            return True
        return False

    def _error(self, code):
        self._error_code = code

    def error_code(self):
        return self._error_code

    def start(self):
        self.io_loop().add_callback(self._continue)

    def _continue(self):
        # 1. server_add
        if self._process['server_add'] == 0:
            return self._do_server_add()

        # 2. server_ready
        if self._process['server_ready'] == 0:
            return self._do_server_ready()

        # 3. snapshot_create
        if self._process['snapshot_create'] == 0:
            return self._do_snapshot_create()

        # 4. snapshot_ready
        if self._process['snapshot_ready'] == 0:
            return self._do_snapshot_ready()

        # 5. snapshot_save
        if self._process['snapshot_save'] == 0:
            return self._do_snapshot_save()

        # 6. server_kill
        if self._process['server_kill'] == 0:
            return self._do_server_kill()

    def _do_server_add(self):
        self._process['server_add'] = 1

        # construct cloud-init script from build script
        cloud_init = self._settings['script']
        cloud_init += '\n\n'

        # write to meta-data: nexel-ready=True
        #cloud_init += 'echo "#!/usr/bin/env python\n'
        cloud_init += 'echo "import urllib2 # adapt for python 3+\n' #TODO
        cloud_init += 'import json\n'
        cloud_init += '\n'
        cloud_init += 'tenant_id = \'%s\'\n' % self._auth['tenant_id']
        cloud_init += 'username = \'%s\'\n' % self._auth['username']
        cloud_init += 'password = \'%s\'\n' % self._auth['password']
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
        cloud_init += 'python ~/nexel-ready.py\n'
        cloud_init += 'rm -rf ~/nexel-ready.py\n'

        # boot the server, get srv_id
        # mach = self._settings
        body = {'server': {'name': self._mach_name,
                           'imageRef': self._settings['image_id'],
                           'flavorRef': self._settings['flavor_id'],
                           #'security_groups': [{'name': 'ssh'}],
                           #'key_name': 'Web-Keypair',
                           'user_data': base64.b64encode(cloud_init),
                           'metadata': {'nexel-type': 'snapshot',
                                        'nexel-ready': 'False'}}}
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
            except:
                logger.exception(e)
                self._error(500)
                return
            logger.debug("Added the server succesfully")
            self._server_id = server_id
            self._process['server_add'] = 2
            self._continue()
        req = OpenStackRequest(self._acc_name, 'POST', '/servers', body=body)
        make_request_async(req, callback)

    def _do_server_ready_op(self):
        def callback(resp):
            try:
                j = json.loads(resp.body)
                if j['meta']['nexel-ready'].lower() == 'true':
                    self._server_ready = True
                    self._process['server_ready'] = 2
            except:
                pass
            if self._process['server_ready'] == 2:
                #self._continue()
                self.io_loop().add_timeout(BUILD_DELAY, self._continue)
                return
            self.io_loop().add_timeout(BUILD_DELAY, self._do_server_ready_op)
        req = OpenStackRequest(self._acc_name, 'GET', '/servers/'+self._server_id+'/metadata/nexel-ready')
        make_request_async(req, callback)

    def _do_server_ready(self):
        self._process['server_ready'] = 1
        self.io_loop().add_timeout(BUILD_DELAY, self._do_server_ready_op)

    def _do_snapshot_create(self):
        self._process['snapshot_create'] = 1
        self._snapshot_name = '%s (Generated by Nexel on %s)' % (self._mach_name, datetime.datetime.now().isoformat())
        body = {'createImage': {'name': self._snapshot_name}}
        def callback(resp):
            try:
                assert resp.code == 202
            except:
                self._error(500)
                return
            logger.debug("Created the snapshot succesfully")
            self._process['snapshot_create'] = 2
            self._continue()
        url = '/servers/%s/action' % self._server_id
        req = OpenStackRequest(self._acc_name, 'POST', url, body=body)
        make_request_async(req, callback)

    def _do_snapshot_ready_op(self):
        def callback(resp):
            try:
                assert resp.code == 200
                j = json.loads(resp.body)
                assert len(j['images']) <= 1
                if len(j['images']) == 1:
                    self._os_snapshot_id = j['images'][0]['id']
                    self._process['snapshot_ready'] = 2
            except:
                self._error(500)
                return
            if self._process['snapshot_ready'] == 2:
                #self._continue()
                self.io_loop().add_timeout(SNAPSHOT_DELAY, self._continue)
                return
            self.io_loop().add_timeout(SNAPSHOT_DELAY, self._do_snapshot_ready_op)
        url = '/images?%s' % urllib.urlencode({'name': self._snapshot_name,
                                               'status': 'ACTIVE'})
        req = OpenStackRequest(self._acc_name, 'GET', url)
        make_request_async(req, callback)

    def _do_snapshot_ready(self):
        self._process['snapshot_ready'] = 1
        self.io_loop().add_timeout(SNAPSHOT_DELAY, self._do_snapshot_ready_op)

    def _do_snapshot_save(self):
        self._process['snapshot_save'] = 1
        # save self._os_snapshot_id into boot.conf :: vm :: snapshot-id
        # file may not exist!, could be in a strange state
        logger.debug("Snapshot ID: "+self._os_snapshot_id)
        self._process['snapshot_save'] = 2
        logger.debug("Saved the snapshot succesfully")
        self._continue()

    def _do_server_kill(self):
        self._process['server_kill'] = 1

        def callback(resp):
            if not http_success(resp.code):
                self._error(500)
                return
            self._process['server_kill'] = 2
            logger.debug("Killed the server succesfully")
            self._continue()
        url = '/servers/%s' % self._server_id
        req = OpenStackRequest(self._acc_name, 'DELETE', url)
        make_request_async(req, callback)
