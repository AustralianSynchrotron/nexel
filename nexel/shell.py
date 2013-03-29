import argparse
import json
import requests
import sys

# TODO: where should these settings come from? (environment variable?)
SERVER = 'http://localhost'
PORT = '8888'

# TODO: ensure parsed <account_name> and <machine_name> are URL-safe

# TODO: "nexel check snapshot health"?

# TODO: "nexel get warnings"... list of current warnings with the filesystem

# "nexel"
parser = argparse.ArgumentParser(prog=sys.argv[0],
                                 description='Nexel Shell: Build and launch self-managed OpenStack instances for multiple tenants.')
subparsers = parser.add_subparsers(help='commands')

# "nexel list-accounts"
list_accounts_parser = subparsers.add_parser('list-accounts',
                                             help='Print a list of all available accounts.')
list_accounts_parser.set_defaults(command='list-accounts')
list_accounts_parser.set_defaults(method='GET')
list_accounts_parser.set_defaults(request='/accounts')

# "nexel account-info"
account_info_parser = subparsers.add_parser('account-info',
                                            help='Show information of a specified account.')
account_info_parser.add_argument('<account_name>', action='store',
                                 help='Name of the account to query for information.')
account_info_parser.set_defaults(command='account-info')
account_info_parser.set_defaults(method='GET')
account_info_parser.set_defaults(request='/accounts/<account_name>')

# "nexel list-machines"
list_machines_parser = subparsers.add_parser('list-machines',
                                             help='Print a list of all available machines in a specified account.')
list_machines_parser.add_argument('<account_name>', action='store',
                                 help='Name of the account to query for the list of machines.')
list_machines_parser.set_defaults(command='list-machines')
list_machines_parser.set_defaults(method='GET')
list_machines_parser.set_defaults(request='/accounts/<account_name>/machines')

# "nexel machine-info"
machine_info_parser = subparsers.add_parser('machine-info',
                                            help='Show information about a specified machine.')
machine_info_parser.add_argument('<account_name>', action='store',
                                 help='Name of the account that owns the machine.')
machine_info_parser.add_argument('<machine_name>', action='store',
                                 help='Name of the machine to query for information.')
machine_info_parser.set_defaults(command='machine-info')
machine_info_parser.set_defaults(method='GET')
machine_info_parser.set_defaults(request='/accounts/<account_name>/machines/<machine_name>')

# "nexel snapshot-info"
snapshot_info_parser = subparsers.add_parser('snapshot-info',
                                             help='Show information about a specified machine\'s snapshot.')
snapshot_info_parser.add_argument('<account_name>', action='store',
                                  help='Name of the account that owns the machine.')
snapshot_info_parser.add_argument('<machine_name>', action='store',
                                  help='Name of the machine to query for snapshot information.')
snapshot_info_parser.set_defaults(command='snapshot-info')
snapshot_info_parser.set_defaults(method='GET')
snapshot_info_parser.set_defaults(request='/accounts/<account_name>/machines/<machine_name>/snapshot')

# "nexel build-snapshot"
build_snapshot_parser = subparsers.add_parser('build-snapshot',
                                              help='Create the snapshot of a specified machine.')
build_snapshot_parser.add_argument('<account_name>', action='store',
                                   help='Name of the account that owns the machine.')
build_snapshot_parser.add_argument('<machine_name>', action='store',
                                   help='Name of the machine to build the snapshot.')
build_snapshot_parser.set_defaults(command='build-snapshot')
build_snapshot_parser.set_defaults(method='POST')
build_snapshot_parser.set_defaults(request='/accounts/<account_name>/machines/<machine_name>/snapshot')

# "nexel rebuild-snapshot"
rebuild_snapshot_parser = subparsers.add_parser('rebuild-snapshot',
                                                help='Rebuild the snapshot of a specified machine.')
rebuild_snapshot_parser.add_argument('<account_name>', action='store',
                                     help='Name of the account that owns the machine.')
rebuild_snapshot_parser.add_argument('<machine_name>', action='store',
                                     help='Name of the machine to rebuild the snapshot.')
rebuild_snapshot_parser.set_defaults(command='rebuild-snapshot')
rebuild_snapshot_parser.set_defaults(method='PUT')
rebuild_snapshot_parser.set_defaults(request='/accounts/<account_name>/machines/<machine_name>/snapshot')

# "nexel delete-snapshot"
delete_snapshot_parser = subparsers.add_parser('delete-snapshot',
                                              help='Delete the snapshot of a specified machine.')
delete_snapshot_parser.add_argument('<account_name>', action='store',
                                    help='Name of the account that owns the machine.')
delete_snapshot_parser.add_argument('<machine_name>', action='store',
                                    help='Name of the machine to delete the snapshot.')
delete_snapshot_parser.set_defaults(command='delete-snapshot')
delete_snapshot_parser.set_defaults(method='DELETE')
delete_snapshot_parser.set_defaults(request='/accounts/<account_name>/machines/<machine_name>/snapshot')

# "nexel launch-instance"
launch_instance_parser = subparsers.add_parser('launch-instance',
                                               help='Launch an instance from the snapshot of a specified machine.')
launch_instance_parser.add_argument('<account_name>', action='store',
                                    help='Name of the account that owns the machine.')
launch_instance_parser.add_argument('<machine_name>', action='store',
                                    help='Name of the machine to launch an instance from the snapshot.')
launch_instance_parser.set_defaults(command='launch-instance')
launch_instance_parser.set_defaults(method='POST')
launch_instance_parser.set_defaults(request='/accounts/<account_name>/machines/<machine_name>/instance')

"""
# "nexel instance-info"
instance_info_parser = subparsers.add_parser('instance-info',
                                             help='Show information about a specified instances.')
instance_info_parser.add_argument('<account_name>', action='store',
                                  help='Name of the account that owns the machine.')
instance_info_parser.add_argument('<machine_name>', action='store',
                                  help='Name of the machine .....') # TODO
instance_info_parser.set_defaults(command='launch-instance')
instance_info_parser.set_defaults(method='POST')
instance_info_parser.set_defaults(request='/accounts/<account_name>/machines/<machine_name>/instance')
"""

# "nexel list-servers"
list_servers_parser = subparsers.add_parser('list-servers',
                                            help='Print a list of all running servers in a specified account.')
list_servers_parser.add_argument('<account_name>', action='store',
                                 help='Name of the account to query for the list of servers.')
list_servers_parser.set_defaults(command='list-servers')
list_servers_parser.set_defaults(method='GET')
list_servers_parser.set_defaults(request='/accounts/<account_name>/servers')

# "nexel server-log"
server_log_parser = subparsers.add_parser('server-log',
                                          help='Show the console output log for the specified server.')
server_log_parser.add_argument('<account_name>', action='store',
                               help='Name of the account that owns the server.')
server_log_parser.add_argument('<server_id>', action='store',
                               help='OpenStack ID of the server.')
server_log_parser.set_defaults(command='server-log')
server_log_parser.set_defaults(method='GET')
server_log_parser.set_defaults(request='/accounts/<account_name>/servers/<server_id>/log')

# "nexel quota"
quota_parser = subparsers.add_parser('quota',
                                     help='Print the current quota information for the specified account.')
quota_parser.add_argument('<account_name>', action='store',
                          help='Name of the account to query for quota information.')
quota_parser.set_defaults(command='quota')
quota_parser.set_defaults(method='GET')
quota_parser.set_defaults(request='/accounts/<account_name>/quota')

# "nexel flavors"
flavor_parser = subparsers.add_parser('flavors',
                                      help='Print the available server flavors for the specified account.')
flavor_parser.add_argument('<account_name>', action='store',
                           help='Name of the account to query for server flavor information.')
flavor_parser.set_defaults(command='flavors')
flavor_parser.set_defaults(method='GET')
flavor_parser.set_defaults(request='/accounts/<account_name>/flavors')


def main():
    # process command line
    args = vars(parser.parse_args())

    # construct url
    def _replace_all(text, dic):
        for i, j in dic.iteritems():
            if i[0] == '<' and i[-1] == '>':
                text = text.replace(i, j)
        return text
    request = _replace_all(args['request'], args)
    url = '%s:%s%s' % (SERVER, PORT, request)
    print 'Request:', args['method'], url

    # make request
    m = args['method']
    #try:
    if m == 'GET':
        r = requests.get(url)
    elif m == 'POST':
        r = requests.post(url)
    elif m == 'PUT':
        r = requests.put(url)
    elif m == 'DELETE':
        r = requests.delete(url)
    else:
        raise ValueError()
    #except:
    #    sys.exit('*** Error: Nexel daemon not running')

    print 'Response:'
    try:
        if args['command'] == 'server-log':
            print json.loads(r.content)['output']
        else:
            print json.dumps(json.loads(r.content), sort_keys=True, indent=4, separators=(',', ': '))
    except:
        print 'No json'
