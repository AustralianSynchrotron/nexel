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

    # [server]
    #d['server_name'] = conf.get('server', 'name') # redundant
    d['server_port'] = int(conf.get('server', 'port'))
    s = conf.get('server', 'restrict-to')
    d['server_restrict_to'] = s.replace(',', ' ').replace(';', ' ').split()

    # [os]
    d['os_auth_url'] = conf.get('os', 'auth-url')
    d['os_nova_url'] = conf.get('os', 'nova-url')

    # [config]
    d['accounts_path'] = __read_path(conf.get('config', 'accounts-path'), cwd)
    d['datamounts_path'] = \
        __read_path(conf.get('config', 'datamounts-path'), cwd)

    # [time]
    d['server_ip_refresh']    = conf.get('time', 'server-ip-refresh')
    d['server_ready_refresh'] = conf.get('time', 'server-ready-refresh')
    d['init_shutdown']        = conf.get('time', 'init-shutdown')
    d['nx_logout_shutdown']   = conf.get('time', 'nx-logout-shutdown')
    d['launch_timeout']       = conf.get('time', 'launch-timeout')

    # update singleton
    Settings().clear()
    Settings().update(d)
