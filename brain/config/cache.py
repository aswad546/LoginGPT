from flask_caching import Cache


cache = Cache()


def config_cache(app):
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_HOST"] = app.config["REDIS_HOST"]
    app.config["CACHE_REDIS_PORT"] = app.config["REDIS_PORT"]
    app.config["CACHE_KEY_PREFIX"] = "webcache"
    app.config["CACHE_SOURCE_CHECK"] = True
    app.config["CACHE_DEFAULT_TIMEOUT"] = 86400 # 1 day
    cache.init_app(app)
