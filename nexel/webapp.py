import logging
from nexel.config.settings import Settings
from nexel.handlers import dispatcher
import tornado.options
import tornado.web

DEBUG = True


def install():
    web_app = tornado.web.Application(dispatcher, debug=DEBUG)
    web_app.listen(Settings()['server_port'])
    tornado.options.enable_pretty_logging()
    logging.getLogger().setLevel(logging.INFO)
    return web_app
