from modules.rabbit import Rabbit


def config_rabbitmq(app):
    host = app.config["RABBITMQ_HOST"]
    port = app.config["RABBITMQ_PORT"]
    user = app.config["ADMIN_USER"]
    password = app.config["ADMIN_PASS"]
    rabbit = Rabbit(host, port, user, password)
    app.extensions["rabbit"] = rabbit
    app.config["rabbit"] = rabbit # deprecated
