from uuid import uuid4
from apiflask import APIBlueprint
from apiflask.fields import String
from flask import current_app
from modules.auth import admin_auth


bp_tags = APIBlueprint("tags", __name__, url_prefix="/tags")


@bp_tags.get("/")
def get_tags():
    db = current_app.config["db"]
    result = list(db["scan_tags"].find({}, {"_id": 0}))
    return {"success": True, "error": None, "data": result}


@bp_tags.put("/")
@bp_tags.auth_required(admin_auth)
@bp_tags.input({
    "scan_id": String(required=True),
    "tag_name": String(required=True)
}, location="query")
def add_tag(query_data):
    db = current_app.config["db"]
    scan_id = query_data["scan_id"]
    tag_name = query_data["tag_name"]

    if db["scan_tags"].count_documents({"tag_name": tag_name}):
        db["scan_tags"].update_one({"tag_name": tag_name}, {"$addToSet": {"scan_ids": scan_id}})
    else:
        db["scan_tags"].insert_one({"tag_id": str(uuid4()), "tag_name": tag_name, "scan_ids": [scan_id]})

    return {"success": True, "error": None, "data": None}


@bp_tags.delete("/")
@bp_tags.auth_required(admin_auth)
@bp_tags.input({
    "scan_id": String(required=True),
    "tag_name": String(required=True)
}, location="query")
def delete_tag(query_data):
    db = current_app.config["db"]
    scan_id = query_data["scan_id"]
    tag_name = query_data["tag_name"]

    db["scan_tags"].update_one({"tag_name": tag_name}, {"$pull": {"scan_ids": scan_id}})
    if not db["scan_tags"].find_one({"tag_name": tag_name})["scan_ids"]:
        db["scan_tags"].delete_one({"tag_name": tag_name})

    return {"success": True, "error": None, "data": None}
