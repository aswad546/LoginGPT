import requests
from apiflask import APIBlueprint
from flask import request, current_app
from modules.auth import admin_auth


bp_rabbit = APIBlueprint("rabbit", __name__, url_prefix="/rabbit")


@bp_rabbit.get("/<path:url>")
def request_rabbitmq_get_endpoint(url):
    host = current_app.config["RABBITMQ_HOST"]
    port = current_app.config["RABBITMQ_PORT_API"]
    user = current_app.config["ADMIN_USER"]
    passwd = current_app.config["ADMIN_PASS"]
    r = requests.get(f"http://{host}:{port}/api/{url}", auth=(user, passwd))
    if r.status_code == 200:
        return {"success": True, "error": None, "data": r.json()}
    elif r.status_code == 204:
        return {"success": True, "error": None, "data": None}
    else:
        return {"success": False, "error": f"{r.status_code}", "data": None}


@bp_rabbit.route("/<path:url>", methods=["POST", "PUT", "DELETE"])
@bp_rabbit.auth_required(admin_auth)
def request_rabbitmq_post_put_delete_endpoint(url):
    host = current_app.config["RABBITMQ_HOST"]
    port = current_app.config["RABBITMQ_PORT_API"]
    user = current_app.config["ADMIN_USER"]
    passwd = current_app.config["ADMIN_PASS"]
    r = getattr(requests, request.method.lower())(
        f"http://{host}:{port}/api/{url}", auth=(user, passwd)
    )
    if r.status_code == 200:
        return {"success": True, "error": None, "data": r.json()}
    elif r.status_code == 204:
        return {"success": True, "error": None, "data": None}
    else:
        return {"success": False, "error": f"{r.status_code}", "data": None}
