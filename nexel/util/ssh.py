import Crypto.Random
import logging
import multiprocessing
import os
from os.path import join
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
logger.setLevel(logging.INFO)


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


def __add_key_to_data_server_async(dataserver, ssh_key, uid):
    logger.debug('in __add_key_to_data_server_async [%d]' % os.getpid())
    try:
        domain = Datamounts()[dataserver]['server']['domain']
        login = Datamounts()[dataserver]['root']['username']
        path_to_key = Datamounts()[dataserver]['root']['private_key']
    except Exception, e:
        logger.exception(e)
        return False

    # connect to datamount server
    try:
        client = paramiko.SSHClient()
        client.load_host_keys(path_to_key)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(domain, username=login)
    except Exception, e:
        logger.exception(e)
        return False

    # get user's home dir
    _, stdout, stderr = \
        client.exec_command('getent passwd "%s" | cut -d: -f6' % uid)
    stderr = stderr.read()
    if (stderr != '') or (stdout == ''):
        client.close()
        logger.error("The username on the datamount is not valid: '%s'"%stderr)
        return False
    try:
        home = stdout.read().strip()
        if not home.startswith("/home/"):
            raise ValueError("Wrong home directory given: '%s'"%home)
    except Exception, e:
        logger.exception(e)
        client.close()
        return False

    # logger.debug('got user home dir: %s' % home)
    # check/create home and .ssh directories
    dotssh = join(home, '.ssh')
    command = '[ ! -d %s ] && mkdir -p %s '\
            '&& chown -R `id -u %s`:`id -g %s` %s' % \
            (dotssh, dotssh, uid, uid, dotssh)
    # logger.debug(command)
    _, stdout, stderr = \
        client.exec_command(command)
    stderr = stderr.read()
    if stderr != '':
        client.close()
        logger.error(stderr)
        return False

    # append public key to authorized keys
    keys = join(dotssh, 'authorized_keys')
    pubkey = ssh_key.strip().replace('\"', '\\\"')
    command = '[ -e %s ] && echo "%s" >> %s || '\
        '(echo "%s" > %s && chown`id -u %s`:`id -g %s` %s)' \
        % (keys, pubkey, keys, pubkey, keys, uid, uid, keys)
    # logger.debug(command)
    _, stdout, stderr = client.exec_command(command)
    stderr = stderr.read()
    if stderr != '':
        client.close()
        logger.error(stderr)
        return False

    client.close()
    return True


def add_key_to_data_server_async(callback, dataserver, key_pub, username):
    logger.debug('in add_key_to_data_server [%d]' % os.getpid())
    __pool.apply_async(__add_key_to_data_server_async,
                       (dataserver, key_pub, username),
                       callback=callback)
    #sync method for debugging...
    #result = \
    #    __add_key_to_data_server_async(dataserver, key_pub, username)
    #callback(result)


# setup processing pools
__manager = multiprocessing.Manager()
__pool = multiprocessing.Pool(processes=PROC_POOL)


# setup auto-reload teardown
def __kill_pool():
    __pool.terminate()
    __manager.shutdown()
tornado.autoreload.add_reload_hook(__kill_pool)
