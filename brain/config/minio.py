from minio import Minio


def config_minio(app):
    minio_host = app.config["MINIO_HOST"]
    minio_port = app.config["MINIO_PORT"]
    admin_user = app.config["ADMIN_USER"]
    admin_pass = app.config["ADMIN_PASS"]

    minio = Minio(endpoint=f"{minio_host}:{minio_port}", access_key=admin_user, secret_key=admin_pass, secure=False)

    buckets = [
        # screenshots
        "login-page-candidate-screenshot", "idp-screenshot",
        "keyword-recognition-screenshot", "logo-recognition-screenshot",
        "login-trace-screenshot",
        # har
        "idp-har", "login-page-analysis-har", "login-trace-har",
        # json
        "element-tree-markup", "metadata-data", "robots", "sitemap",
        "login-trace-storage-state"
    ]
    for bucket in buckets:
        if not minio.bucket_exists(bucket):
            minio.make_bucket(bucket)

    app.extensions["minio"] = minio
    app.config["objstore"] = minio # deprecated
