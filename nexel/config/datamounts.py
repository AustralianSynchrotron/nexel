import ConfigParser
import datetime
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
        datamount_path = os.path.join(datamounts_path, datamount_name)
        if not os.path.isdir(datamount_path):
            continue
        if RX_NAMES.match(datamount_name) is None:
            continue
        # read auth.conf (if exists)
        try:
            auth = ConfigParser.ConfigParser()
            auth.read(os.path.join(datamount_path, 'auth.conf'))
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
