from raven import Client
from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging
from raven.contrib.tornado import AsyncSentryClient

# log level settings
DEBUG = False
logging.getLogger().setLevel(logging.INFO)

def install():
    import logging
    from nexel.config.settings import Settings
    from nexel.handlers import dispatcher
    from tornado import version_info
    if version_info[0] >= 3:
        import tornado.log
        tornado.log.enable_pretty_logging()
    else:
        import tornado.options
        tornado.options.enable_pretty_logging()

    # webapp
    import tornado.web
    web_app = tornado.web.Application(dispatcher, debug=DEBUG)
    web_app.listen(Settings()['server_port'])

    # sentry logging
    if Settings()['sentry-api-key']:
        web_app.sentry_client = AsyncSentryClient(Settings()['sentry-api-key'])
        setup_logging(SentryHandler(Client(Settings()['sentry-api-key'])))

    return web_app
