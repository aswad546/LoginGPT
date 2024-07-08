def config_flask(app):
    app.url_map.strict_slashes = False
    app.jinja_env.policies["json.dumps_kwargs"] = {"sort_keys": False}
    app.servers = [
        {"name": "Production", "url": f"//{app.config['BRAIN_EXTERNAL_DOMAIN']}"},
        {"name": "Development", "url": "//localhost:8080"}
    ]
