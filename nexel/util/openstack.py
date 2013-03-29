from tornado import httpclient
from tornado.web import HTTPError
import json

from nexel.config.accounts import Accounts
from nexel.config.settings import Settings


class OpenStackRequest(object):
    def __init__(self, acc_name, method, url, body=None):
        self.acc_name = acc_name
        self.method = method
        self.url = url
        self.body = body


def http_success(code):
    code_num = int(code)
    if code_num < 200:
        return False
    if code_num >= 300:
        return False
    return True


def login_async(acc_name, callback_final):
    def callback(resp):
        if not http_success(resp.code):
            raise HTTPError(resp.code)
        try:
            j = json.loads(resp.body)
            token = j['access']['token']['id']
        except:
            raise HTTPError(500)
        callback_final(token)
    url = Settings()['os_auth_url'] + '/tokens'
    headers = {'Content-Type': 'application/json'}
    auth = Accounts()[acc_name]['auth']
    body = {'auth': {'passwordCredentials': {'username': auth['username'],
                                             'password': auth['password']},
                     'tenantId': auth['tenant_id']}}
    jbody = json.dumps(body, separators=(',', ':'))
    http_client = httpclient.AsyncHTTPClient()
    http_client.fetch(url,
                      callback,
                      method='POST',
                      headers=headers,
                      body=jbody,
                      validate_cert=False)


def make_request_async(req, callback_final):
    def callback_login(token):
        url = '/'.join([Settings()['os_nova_url'],
                        Accounts()[req.acc_name]['auth']['tenant_id'],
                        req.url])
        headers = {'X-Auth-Token': token}
        if req.body is not None:
            headers['Content-Type'] = 'application/json'
            jbody = json.dumps(req.body, separators=(',', ':'))
        else:
            jbody = None
        http_client = httpclient.AsyncHTTPClient()
        http_client.fetch(url,
                          callback_final,
                          method=req.method,
                          headers=headers,
                          body=jbody,
                          validate_cert=False)
    login_async(req.acc_name, callback_login)
