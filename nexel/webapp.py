DEBUG = True


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
    import tornado.web
    web_app = tornado.web.Application(dispatcher, debug=DEBUG)
    web_app.listen(Settings()['server_port'])
    logging.getLogger().setLevel(logging.INFO)
    return web_app
