import json
import logging
from tornado.web import RequestHandler, HTTPError, asynchronous

from nexel.config.accounts import Accounts
from nexel.launch import LaunchProcess
from nexel.snapshot import SnapshotProcess
# TODO: make_request_async should be a method on OpenStackReq
from nexel.util.openstack \
import OpenStackRequest, make_request_async, http_success


logger = logging.getLogger(__name__)


class NexelRequestHandler(RequestHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')

    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')


class CatchAll(NexelRequestHandler):
    pass


class ListAllAccounts(NexelRequestHandler):
    def get(self):
        self.write({'output': Accounts().keys()})


class AccountInfo(NexelRequestHandler):
    def get(self, acc_name):
        try:
            self.write({'output': {'auth': Accounts()[acc_name]['auth']}})
        except:
            raise HTTPError(404)


class ListAllMachines(NexelRequestHandler):
    def get(self, acc_name):
        try:
            self.write({'output': Accounts()[acc_name]['machines'].keys()})
        except:
            raise HTTPError(404)


class MachineInfo(NexelRequestHandler):
    def get(self, acc_name, mach_name):
        try:
            self.write({'output': Accounts()[acc_name]['machines'][mach_name]})
        except:
            raise HTTPError(404)


class SnapshotActions(NexelRequestHandler):
    def get(self, acc_name, mach_name):
        raise NotImplementedError

    @asynchronous
    def post(self, acc_name, mach_name):
        # create and start snapshot process
        try:
            sp = SnapshotProcess(acc_name, mach_name)
            sp.start()
        except HTTPError as e:
            raise e
        except:
            raise HTTPError(500)

        # return snapshot id
        self.set_status(202)
        self.write({'output': {'snapshot_id': sp.snapshot_id()}})
        self.finish()

    def delete(self, acc_name, mach_name):
        raise NotImplementedError


class LaunchInstance(NexelRequestHandler):
    @asynchronous
    def post(self, acc_name, mach_name):
        # get user information
        try:
            j = json.loads(self.request.body)
            auth_type = j['auth_type']
            auth_value = j['auth_value'].strip()
        except Exception, e:
            logger.exception(e)
            raise HTTPError(400)

        # create and start launch process
        try:
            lp = LaunchProcess(acc_name, mach_name, auth_type, auth_value)
            lp.start()
        except HTTPError as e:
            raise e
        except Exception, e:
            logger.exception(e)
            raise HTTPError(500)

        # return launch id
        self.set_status(202)
        self.write({'output': {'launch_id': lp.launch_id()}})
        self.finish()


class ListAllServers(NexelRequestHandler):
    @asynchronous
    def get(self, acc_name):
        def callback(resp):
            if not http_success(resp.code):
                raise HTTPError(resp.code)
            try:
                j = json.loads(resp.body)
                out = []
                for srv in j['servers']:
                    addr = srv['addresses']
                    try:
                        ip_address = addr[addr.keys()[0]][0]['addr']
                    except:
                        ip_address = ''
                    # TODO: meta-data to detect a Nexel instance or snapshot in process
                    out.append({'id': srv['id'],
                                'name': srv['name'],
                                'created': srv['created'],
                                'ip_address': ip_address})
                self.write({'output': out})
            except:
                raise HTTPError(500)
            self.finish()
        req = OpenStackRequest(acc_name, 'GET', '/servers/detail')
        make_request_async(req, callback)


class ServerActions(NexelRequestHandler):
    @asynchronous
    def get(self, acc_name, srv_id):
        def callback(resp):
            if not http_success(resp.code):
                raise HTTPError(resp.code)
            self.write({'output': json.loads(resp.body)})
            self.finish()
        req = OpenStackRequest(acc_name, 'GET', '/servers/' + srv_id)
        make_request_async(req, callback)

    @asynchronous
    def delete(self, acc_name, srv_id):
        def callback(resp):
            if not http_success(resp.code):
                raise HTTPError(resp.code)
            self.finish()
        req = OpenStackRequest(acc_name, 'DELETE', '/servers/' + srv_id)
        make_request_async(req, callback)


class GetServerIp(NexelRequestHandler):
    @asynchronous
    def get(self, acc_name, srv_id):
        def callback(resp):
            if not http_success(resp.code):
                raise HTTPError(resp.code)
            try:
                j = json.loads(resp.body)
                addr = j['server']['addresses']
                ip_address = addr[addr.keys()[0]][0]['addr']
            except:
                ip_address = ''
            self.write({'output': {'ip_address': ip_address}})
            self.finish()
        req = OpenStackRequest(acc_name, 'GET', '/servers/' + srv_id)
        make_request_async(req, callback)


class GetServerLog(NexelRequestHandler):
    @asynchronous
    def get(self, acc_name, srv_id):
        def callback(resp):
            if not http_success(resp.code):
                raise HTTPError(resp.code)
            try:
                j = json.loads(resp.body)
                log = j['output']
            except:
                log = ''
            self.write({'output': log})
            self.finish()
        body = {'os-getConsoleOutput': {}}
        req = OpenStackRequest(acc_name, 'POST', '/servers/'+srv_id+'/action', body=body)
        make_request_async(req, callback)


class QuotaInfo(NexelRequestHandler):
    @asynchronous
    def get(self, acc_name):
        def callback(resp):
            if not http_success(resp.code):
                raise HTTPError(resp.code)
            try:
                j = json.loads(resp.body)
                limits = j['limits']['absolute']
                self.write({'output': {
                    'servers': [limits['totalInstancesUsed'],
                                limits['maxTotalInstances']],
                    'cores': [limits['totalCoresUsed'],
                              limits['maxTotalCores']],
                    'ram': [limits['totalRAMUsed'],
                            limits['maxTotalRAMSize']]}})
            except:
                raise HTTPError(500)
            self.finish()
        req = OpenStackRequest(acc_name, 'GET', '/limits')
        make_request_async(req, callback)


class ListAllFlavors(NexelRequestHandler):
    @asynchronous
    def get(self, acc_name):
        def callback(resp):
            if not http_success(resp.code):
                raise HTTPError(resp.code)
            self.write({'output': json.loads(resp.body)})
            self.finish()
        req = OpenStackRequest(acc_name, 'GET', '/flavors')
        make_request_async(req, callback)


class ListAllInstances(NexelRequestHandler):
    def get(self):
        self.write({'output': LaunchProcess.all_ids()})


class GetInstanceInfo(NexelRequestHandler):
    def get(self, launch_id):
        lp = LaunchProcess.get(launch_id)
        if lp is None:
            raise HTTPError(404)
        ipAddr = ""
        if lp.ip_address() != None:
            ipAddr = lp.ip_address()
        out = {'account_name': lp.account_name(),
               'server_id': '',
               'status': lp.status(),
               'ip_address': ipAddr,
               'error_code': 0,
               'server_ready' : lp.server_ready()}
        err = lp.error_code()
        if err is not None:
            out['error_code'] = err
        else:
            if lp.server_ready():
                out['server_id'] = lp.server_id()
        self.write({'output': out})


dispatcher = [
    (r'/accounts', ListAllAccounts),
    (r'/accounts/([0-9a-zA-Z\-\_]+)', AccountInfo),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/machines', ListAllMachines),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/machines/([0-9a-zA-Z\-\_]+)', MachineInfo),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/machines/([0-9a-zA-Z\-\_]+)/snapshot', SnapshotActions),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/machines/([0-9a-zA-Z\-\_]+)/instance', LaunchInstance),
    #(r'/accounts/([0-9a-zA-Z\-\_]+)/instances', ListAllInstances), # filter with meta-data?
    (r'/accounts/([0-9a-zA-Z\-\_]+)/servers', ListAllServers),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/servers/([0-9a-f\-]+)', ServerActions),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/servers/([0-9a-f\-]+)/ip', GetServerIp),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/servers/([0-9a-f\-]+)/log', GetServerLog),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/servers/([0-9a-f\-]+)/instance-info', GetInstanceInfo),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/quota', QuotaInfo),
    (r'/accounts/([0-9a-zA-Z\-\_]+)/flavors', ListAllFlavors),
    (r'/instances', ListAllInstances),
    (r'/instances/([0-9a-zA-Z\-]+)', GetInstanceInfo),
    # TODO: /datamounts...
    (r'/.*', CatchAll)
]
