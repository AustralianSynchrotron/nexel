import argparse
from tornado.ioloop import IOLoop

from nexel.config import accounts
from nexel.config import datamounts
from nexel.config import settings
from nexel import webapp


def main():
    # aquire path to configuration file
    parser = argparse.ArgumentParser(prog='nexeld',
                                     description='Nexel web-service daemon')
    parser.add_argument('<config_file>', action='store',
                        help='Path to configuration file')
    args = vars(parser.parse_args())
    conf_path = args['<config_file>']

    # start main event loop, read and install services
    settings.read(conf_path)
    datamounts.read_and_install()
    accounts.read_and_install()
    webapp.install()
    IOLoop().instance().start()
