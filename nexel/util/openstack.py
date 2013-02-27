# Copyright (c) 2013, Synchrotron Light Source Australia Pty Ltd
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the Australian Synchrotron nor the names of its contributors
#     may be used to endorse or promote products derived from this software
#     without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from config.accounts import Accounts
from config.settings import Settings
import json
from tornado import httpclient
from tornado.web import HTTPError

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
    url = Settings()['os_auth_url']+'/tokens'
    headers = {'Content-Type': 'application/json'}
    auth = Accounts()[acc_name]['auth']
    body = {'auth': {'passwordCredentials': {'username': auth['username'],
                                             'password': auth['password']},
                     'tenantId': auth['tenant_id']}}
    jbody = json.dumps(body, separators=(',', ':'))
    http_client = httpclient.AsyncHTTPClient()
    http_client.fetch(url, callback, method='POST', headers=headers, body=jbody,
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
        http_client.fetch(url, callback_final, method=req.method, headers=headers,
                          body=jbody, validate_cert=False)
    login_async(req.acc_name, callback_login)

