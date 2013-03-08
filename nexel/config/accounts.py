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
import datetime
import logging
from nexel.config.settings import Settings
import os.path
try:
    import pyinotify
except:
    pyinotify = None
import re
from tornado.ioloop import IOLoop

RX_NAMES = re.compile(r'^[0-9a-zA-Z\-\_]+$')
RX_OS_ID = re.compile(r'^[0-9a-f\-]+$')
UPDATE_DELAY = datetime.timedelta(seconds=1)

class __AccountsSingleton(object):
    d = {}
    lock = [False]

def Accounts():
    return __AccountsSingleton().d

def read_and_install():
    __crawl()
    if pyinotify is not None:
        __install_listener()

def __crawl():
    accounts_path = Settings()['accounts_path']
    if not os.path.isdir(accounts_path):
        raise ValueError('accounts directory does not exist')
    
    # crawl through sub-directories
    m = {}
    for account_name in os.listdir(accounts_path):
        account_path = accounts_path + '/' + account_name
        if not os.path.isdir(account_path):
            continue
        if RX_NAMES.match(account_name) is None:
            continue
        
        # read auth.conf (if exists)
        try:
            auth = ConfigParser.ConfigParser()
            auth.read(account_path + '/auth.conf')
            tenant_id = auth.get('os-credentials', 'tenant-id')
            username = auth.get('os-credentials', 'username')
            password = auth.get('os-credentials', 'password')
        except:
            # TODO: warn the user that the auth.conf file does not exit, or has errors
            continue
        
        # add to model
        m[account_name] = {'auth': {'tenant_id': tenant_id,
                                    'username': username,
                                    'password': password},
                           'machines': {}}
        
        # crawl through machines for this account
        path_to_machines = account_path + '/machines'
        if not os.path.isdir(path_to_machines):
            continue
        for machine_name in os.listdir(path_to_machines):
            machine_path = path_to_machines + '/' + machine_name
            if not os.path.isdir(machine_path):
                continue
            if RX_NAMES.match(machine_name) is None:
                continue
            
            # read boot.conf
            try:
                boot = ConfigParser.ConfigParser()
                boot.read(machine_path + '/boot.conf')
                vm_snapshot_id = boot.get('vm', 'snapshot-id')
                vm_flavor_id = boot.get('vm', 'flavor-id')
                datamounts_datamount = boot.get('datamounts', 'datamount')
            except:
                # TODO: warn the user that the boot.conf file does not exit, or has errors
                continue
            
            m[account_name]['machines'][machine_name] = {}
            m[account_name]['machines'][machine_name]['boot'] = {'snapshot_id': vm_snapshot_id,
                                                                 'flavor_id': vm_flavor_id,
                                                                 'datamount': datamounts_datamount}
            '''
            # minimum requirements:
            #  either build-from.id OR boot-from.id
            build_from_id = __read_os_id(machine_path + '/build-from.id')
            boot_from_id = __read_os_id(machine_path + '/boot-from.id')
            if build_from_id is None and boot_from_id is None:
                continue
            
            # add machine
            m[account_name]['machines'][machine_name] = {}
            if build_from_id is not None:
                m[account_name]['machines'][machine_name]['build'] = {'from_id': build_from_id}
            if boot_from_id is not None:
                m[account_name]['machines'][machine_name]['boot'] = {'from_id': boot_from_id}
            
            # read optional shell scripts (build.sh and boot.sh)
            build_script = __read_shell_script(machine_path + '/build.sh')
            boot_script = __read_shell_script(machine_path + '/boot.sh')
            if build_script is not None:
                if not m[account_name]['machines'][machine_name].has_key('build'):
                    m[account_name]['machines'][machine_name]['build'] = {}
                m[account_name]['machines'][machine_name]['build']['script'] = build_script
            if boot_script is not None:
                if not m[account_name]['machines'][machine_name].has_key('boot'):
                    m[account_name]['machines'][machine_name]['boot'] = {}
                m[account_name]['machines'][machine_name]['boot']['script'] = boot_script
            '''
    
    # update singleton
    Accounts().clear()
    Accounts().update(m)

def __read_os_id(path):
    try:
        f = open(path, 'r')
    except:
        # TODO: warn and advise user
        return None
    try:
        os_id = f.read().split()[0]
    except:
        # TODO: warn and advise user
        return None
    if RX_OS_ID.match(os_id) is None:
        # TODO: warn and advise user
        return None
    return os_id

def __read_shell_script(path):
    try:
        f = open(path, 'r')
    except:
        return None
    s = f.read()
    if not s.startswith('#!/bin/bash\n'):
        # TODO: warn and advise user
        return None
    return s

def __batch_update():
    __AccountsSingleton().lock[0] = False
    __crawl()

def __pyinotify_event(notifier):
    # lock and batch multiple inotify events
    if __AccountsSingleton().lock[0]:
        return
    __AccountsSingleton().lock[0] = True
    io_loop = IOLoop().instance()
    io_loop.add_timeout(UPDATE_DELAY, __batch_update)

def __install_listener():
    accounts_path = Settings()['accounts_path']
    wm = pyinotify.WatchManager()
    #pyinotify.log.setLevel(logging.CRITICAL)
    io_loop = IOLoop().instance()
    notifier = pyinotify.TornadoAsyncNotifier(wm, io_loop, read_freq=1,
                                              callback=__pyinotify_event)
    wm.add_watch(accounts_path, #pyinotify.ALL_EVENTS)
                                pyinotify.IN_CLOSE_WRITE |
                                pyinotify.IN_DELETE |
                                pyinotify.IN_MOVED_TO |
                                pyinotify.IN_MOVED_FROM, rec=True)

