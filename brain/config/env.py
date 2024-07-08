import os


def config_env(app):
    app.config["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")
    app.config["FLASK_DEBUG"] = os.environ.get("FLASK_DEBUG", 0)

    app.config["GUEST_USER"] = os.environ.get("GUEST_USER", "guest")
    app.config["GUEST_PASS"] = os.environ.get("GUEST_PASS", "changeme")
    app.config["ADMIN_USER"] = os.environ.get("ADMIN_USER", "admin")
    app.config["ADMIN_PASS"] = os.environ.get("ADMIN_PASS", "changeme")

    app.config["BRAIN_EXTERNAL_DOMAIN"] = os.environ.get("BRAIN_EXTERNAL_DOMAIN", "brain.docker.localhost")
    app.config["RABBITMQ_EXTERNAL_DOMAIN"] = os.environ.get("RABBITMQ_EXTERNAL_DOMAIN", "rabbitmq.docker.localhost")
    app.config["MONGOEXPRESS_EXTERNAL_DOMAIN"] = os.environ.get("MONGOEXPRESS_EXTERNAL_DOMAIN", "mongoexpress.docker.localhost")
    app.config["MINIO_EXTERNAL_DOMAIN"] = os.environ.get("MINIO_EXTERNAL_DOMAIN", "minio.docker.localhost")
    app.config["JUPYTER_EXTERNAL_DOMAIN"] = os.environ.get("JUPYTER_EXTERNAL_DOMAIN", "jupyter.docker.localhost")

    app.config["RABBITMQ_HOST"] = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    app.config["RABBITMQ_PORT"] = os.environ.get("RABBITMQ_PORT", "5672")
    app.config["RABBITMQ_PORT_API"] = os.environ.get("RABBITMQ_PORT_API", "15672")

    app.config["MONGODB_HOST"] = os.environ.get("MONGODB_HOST", "mongodb")
    app.config["MONGODB_PORT"] = os.environ.get("MONGODB_PORT", "27017")

    app.config["MINIO_HOST"] = os.environ.get("MINIO_HOST", "minio")
    app.config["MINIO_PORT"] = os.environ.get("MINIO_PORT", "9000")

    app.config["REDIS_HOST"] = os.environ.get("REDIS_HOST", "redis")
    app.config["REDIS_PORT"] = os.environ.get("REDIS_PORT", "6379")
