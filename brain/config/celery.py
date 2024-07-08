from celery import Celery, Task


def config_celery(app):
    rabbitmq_host = app.config["RABBITMQ_HOST"]
    rabbitmq_port = app.config["RABBITMQ_PORT"]
    admin_user = app.config["ADMIN_USER"]
    admin_pass = app.config["ADMIN_PASS"]
    mongodb_host = app.config["MONGODB_HOST"]
    mongodb_port = app.config["MONGODB_PORT"]

    app.config["CELERY"] = {
        "broker_url": f"amqp://{admin_user}:{admin_pass}@{rabbitmq_host}:{rabbitmq_port}/",
        "result_backend": f"mongodb://{mongodb_host}:{mongodb_port}",
        "mongodb_backend_settings": {
            "database": "celery",
            "taskmeta_collection": "celery_taskmeta_collection"
        },
        "task_ignore_result": True
    }

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(app.name, task_cls=FlaskTask)
    celery.config_from_object(app.config["CELERY"])
    celery.set_default()
    app.extensions["celery"] = celery
