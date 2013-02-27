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

import Crypto.Random
import multiprocessing
import os
import paramiko
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import tornado.autoreload

RSA_BITS=2048 # 1024 2048 4096
PROC_POOL=4

def __generate_key_async():
    print 'in __generate_key_async [%d]' % os.getpid()
    Crypto.Random.atfork()
    key = paramiko.RSAKey.generate(RSA_BITS)
    public_key = 'ssh-rsa %s' % key.get_base64()
    private_key = StringIO()
    key.write_private_key(private_key)
    private_key.seek(0)
    private_key = private_key.read()
    return (public_key, private_key)

def generate_key_async(callback):
    print 'in generate_key_async [%d]' % os.getpid()
    __pool.apply_async(__generate_key_async, callback=callback)

def __add_key_to_data_server_async(dataserver, ssh_key, username, email):
    print 'in __add_key_to_data_server_async [%d]' % os.getpid()
    
    if username is None:
        auth_value = email
    else:
        auth_value = username
    
    print 'about to start paramiko'
    
    domain = '' # TODO: from Datamounts()
    username = '' # TODO: from Datamounts()
    path_to_key = '' # TODO: from Datamounts()
    
    # connect to datamount server
    try:
        client = paramiko.SSHClient()
        client.load_host_keys(path_to_key)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(domain, username=username)
    except:
        print 'exception whilst connecting to datamount server'
        return False
    
    # check user is on the system, get id (if using email)
    _, stdout, stderr = client.exec_command('id -u %s' % auth_value)
    if stderr.read() != '':
        client.close()
        return False
    if username is None:
        try:
            stdout = stdout.read().strip()
            user_id = str(long(stdout))
        except:
            client.close()
            return False
    else:
        user_id = username
    
    print 'got user_id:', user_id
    
    # check/create home and .ssh directories
    _, stdout, stderr = client.exec_command('mkdir -p /home/%s/.ssh' % user_id) # TODO: use value in Datamounts()
    if stderr.read() != '':
        client.close()
        return False
    
    # append public key to authorized keys
    cmd = 'echo "%s" >> /home/%s/.ssh/authorized_keys' % (ssh_key.strip().replace('\"', '\\\"'),
                                                          user_id) # TODO: use value in Datamounts()
    _, stdout, stderr = client.exec_command(cmd)
    if stderr.read() != '':
        client.close()
        return False
    
    client.close()
    return True

def add_key_to_data_server_async(callback, dataserver, key_pub, username=None, email=None):
    print 'in add_key_to_data_server [%d]' % os.getpid()
    if username is None:
        assert(email is not None)
        assert(email != '')
    if email is None:
        assert(username is not None)
        assert(username != '')
    __pool.apply_async(__add_key_to_data_server_async, (dataserver, key_pub, username, email), callback=callback)

# setup processing pools
__manager = multiprocessing.Manager()
__pool = multiprocessing.Pool(processes=PROC_POOL)

# setup auto-reload teardown
def __kill_pool():
    __pool.terminate()
    __manager.shutdown()
tornado.autoreload.add_reload_hook(__kill_pool)

