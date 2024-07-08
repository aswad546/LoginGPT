from flask_pymongo import PyMongo


def config_mongodb(app):
    mongodb_host = app.config["MONGODB_HOST"]
    mongodb_port = app.config["MONGODB_PORT"]
    app.config["MONGO_URI"] = f"mongodb://{mongodb_host}:{mongodb_port}/sso-monitor"
    mongo = PyMongo(app)
    app.extensions["db"] = mongo.db
    app.config["db"] = mongo.db # deprecated
