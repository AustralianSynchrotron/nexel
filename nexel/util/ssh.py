import Crypto.Random
import logging
import multiprocessing
import os
import paramiko
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import tornado.autoreload

from nexel.config.datamounts import Datamounts


RSA_BITS = 2048  # 1024 2048 4096
PROC_POOL = 4


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def __generate_key_async():
    logger.debug('in __generate_key_async [%d]' % os.getpid())
    Crypto.Random.atfork()
    key = paramiko.RSAKey.generate(RSA_BITS)
    public_key = 'ssh-rsa %s' % key.get_base64()
    private_key = StringIO()
    key.write_private_key(private_key)
    private_key.seek(0)
    private_key = private_key.read()
    return (public_key, private_key)


def generate_key_async(callback):
    logger.debug('in generate_key_async [%d]' % os.getpid())
    __pool.apply_async(__generate_key_async, callback=callback)


def __add_key_to_data_server_async(dataserver, ssh_key, username, email):
    logger.debug('in __add_key_to_data_server_async [%d]' % os.getpid())
    if username is None:
        auth_value = email
    else:
        auth_value = username
    logger.debug('about to start paramiko')
    domain = Datamounts[dataserver]['server']['domain']
    login = Datamounts[dataserver]['root']['username']
    path_to_key = Datamounts[dataserver]['root']['private_key']

    # connect to datamount server
    try:
        client = paramiko.SSHClient()
        client.load_host_keys(path_to_key)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(domain, username=login)
    except Exception, e:
        logger.exception(e)
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

    logger.debug('got user_id:', user_id)

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
    logger.debug('in add_key_to_data_server [%d]' % os.getpid())
    if username is None:
        assert(email is not None)
        assert(email != '')
    if email is None:
        assert(username is not None)
        assert(username != '')
    __pool.apply_async(__add_key_to_data_server_async,
                       (dataserver, key_pub, username, email),
                       callback=callback)

# setup processing pools
__manager = multiprocessing.Manager()
__pool = multiprocessing.Pool(processes=PROC_POOL)


# setup auto-reload teardown
def __kill_pool():
    __pool.terminate()
    __manager.shutdown()
tornado.autoreload.add_reload_hook(__kill_pool)
