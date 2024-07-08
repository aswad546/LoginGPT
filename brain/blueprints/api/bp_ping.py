from apiflask import APIBlueprint


bp_ping = APIBlueprint("ping", __name__, url_prefix="/ping")


@bp_ping.get("/")
def ping():
    return {"success": True, "error": None, "data": "pong"}
