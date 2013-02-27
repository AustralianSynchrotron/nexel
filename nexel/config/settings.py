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

import ConfigParser
import os.path

class __SettingsSingleton(object):
    d = {}

def Settings():
    return __SettingsSingleton().d

def __read_path(path, cwd):
    path = os.path.expanduser(path)
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(cwd, path))

def read(conf_path):
    # read settings config file
    conf = ConfigParser.ConfigParser()
    conf.read(conf_path)
    
    # get current directory of config file
    # (paths in the file can be relative to this location)
    cwd = os.path.abspath(os.path.dirname(conf_path))
    
    # parse into a dictionary
    d = {}
    #d['server_name'] = conf.get('server', 'name') # redundant
    d['server_port'] = int(conf.get('server', 'port'))
    s = conf.get('server', 'restrict-to')
    d['server_restrict_to'] = s.replace(',', ' ').replace(';', ' ').split()
    d['os_auth_url'] = conf.get('os', 'auth-url')
    d['os_nova_url'] = conf.get('os', 'nova-url')
    d['accounts_path'] = __read_path(conf.get('config', 'accounts-path'), cwd)
    d['datamounts_path'] = __read_path(conf.get('config', 'datamounts-path'), cwd)
    
    # update singleton
    Settings().clear()
    Settings().update(d)

