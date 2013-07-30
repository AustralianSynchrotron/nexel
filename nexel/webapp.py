import logging
from raven import Client
from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging
from raven.contrib.tornado import AsyncSentryClient


def webapp_log(handler):
    if handler.get_status() < 400:
        log_method = logging.debug
    elif handler.get_status() < 500:
        log_method = logging.warning
    else:
        log_method = logging.error
    request_time = 1000.0 * handler.request.request_time()
    log_method("%d %s %.2fms", handler.get_status(),
               handler._request_summary(), request_time)


def install():
    from nexel.config.settings import Settings
    from nexel.handlers import dispatcher
    from tornado import version_info
    if version_info[0] >= 3:
        import tornado.log
        tornado.log.enable_pretty_logging()
    else:
        import tornado.options
        tornado.options.enable_pretty_logging()

    # global logging level
    if Settings()['debug']:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    # webapp
    import tornado.web
    web_app = tornado.web.Application(dispatcher, debug=Settings()['debug'],
                                      log_function=webapp_log)
    web_app.listen(Settings()['server_port'])

    # sentry logging
    if Settings()['sentry-api-key']:
        web_app.sentry_client = AsyncSentryClient(Settings()['sentry-api-key'])
        setup_logging(SentryHandler(Client(Settings()['sentry-api-key'])))

    return web_app
