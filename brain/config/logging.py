import logging


def config_logging(app):
    level = getattr(logging, app.config["LOG_LEVEL"].upper())
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s"
    logging.basicConfig(level=level, format=format)
    logging.getLogger("werkzeug").setLevel(level)
