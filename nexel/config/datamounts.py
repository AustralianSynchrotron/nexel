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

RX_NAMES = re.compile(r'^[0-9a-zA-Z\-\_]+$') # TODO: add '\.' for domain names
UPDATE_DELAY = datetime.timedelta(seconds=1)

class __DatamountsSingleton(object):
    d = {}
    lock = [False]

def Datamounts():
    return __DatamountsSingleton().d

def read_and_install():
    __crawl()
    if pyinotify is not None:
        __install_listener()

def __read_path(path, cwd):
    path = os.path.expanduser(path)
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(cwd, path))

def __crawl():
    datamounts_path = Settings()['datamounts_path']
    if not os.path.isdir(datamounts_path):
        raise ValueError('datamounts directory does not exist')
    
    # crawl through sub-directories
    m = {}
    for datamount_name in os.listdir(datamounts_path):
        datamount_path = datamounts_path + '/' + datamount_name
        if not os.path.isdir(datamount_path):
            continue
        if RX_NAMES.match(datamount_name) is None:
            continue
        
        # read auth.conf (if exists)
        try:
            auth = ConfigParser.ConfigParser()
            auth.read(datamount_path + '/auth.conf')
            server_domain = auth.get('server', 'domain')
            server_home_path = auth.get('server', 'home-path')
            root_username = auth.get('root', 'username')
            root_private_key = __read_path(auth.get('root', 'private-key'), datamount_path)
        except:
            # TODO: warn the user that the auth.conf file does not exit, or has errors
            continue
        
        # add to model
        m[datamount_name] = {'server': {'domain': server_domain,
                                        'home_path': server_home_path},
                             'root': {'username': root_username,
                                      'private_key': root_private_key}}
    
    # update singleton
    Datamounts().clear()
    Datamounts().update(m)
    
    print Datamounts()

def __batch_update():
    __DatamountsSingleton().lock[0] = False
    __crawl()

def __pyinotify_event(notifier):
    # lock and batch multiple inotify events
    if __DatamountsSingleton().lock[0]:
        return
    __DatamountsSingleton().lock[0] = True
    io_loop = IOLoop().instance()
    io_loop.add_timeout(UPDATE_DELAY, __batch_update)

def __install_listener():
    datamounts_path = Settings()['datamounts_path']
    wm = pyinotify.WatchManager()
    #pyinotify.log.setLevel(logging.CRITICAL)
    io_loop = IOLoop().instance()
    notifier = pyinotify.TornadoAsyncNotifier(wm, io_loop, read_freq=1,
                                              callback=__pyinotify_event)
    wm.add_watch(datamounts_path, #pyinotify.ALL_EVENTS)
                                  pyinotify.IN_CLOSE_WRITE |
                                  pyinotify.IN_DELETE |
                                  pyinotify.IN_MOVED_TO |
                                  pyinotify.IN_MOVED_FROM, rec=True)

