from time import time
from apiflask import APIBlueprint
from apiflask.fields import String, Integer, Boolean
from apiflask.validators import Range
from flask import current_app
from modules.auth import admin_auth
from modules.helper import find_sibling_data


bp_scans = APIBlueprint("scans", __name__, url_prefix="/scans")


@bp_scans.get("/<task_name>")
@bp_scans.input({
    "offset": Integer(load_default=0, validate=Range(min=0)),
    "limit": Integer(load_default=10, validate=Range(min=1, max=100)),
    "search": String(load_default="")
}, location="query")
def get_scans(task_name, query_data):
    db = current_app.config["db"]
    offset = query_data["offset"]
    limit = query_data["limit"]
    search = query_data["search"]

    sids = set()
    if search:
        for tag in db["scan_tags"].find({"tag_name": {"$regex": search}}):
            sids = sids.union(set(tag["scan_ids"]))
    else:
        sids = set(db[f"{task_name}_tres"].distinct("scan_config.scan_id"))

    total = len(sids)
    result = list(db[f"{task_name}_tres"].aggregate([
        {"$match": {"scan_config.scan_id": {"$in": list(sids)}}},
        {"$group": {
            "_id": "$scan_config.scan_id",
            "first_scan_config": {"$first": "$scan_config"},
            "first_task_config": {"$first": "$task_config"},
            f"first_{task_name}_config": {"$first": f"${task_name}_config"}
        }},
        {"$addFields": {"task_type": f"{task_name}"}}
    ]))
    result = sorted(result, key=lambda x: x["first_task_config"]["task_timestamp_request_sent"], reverse=True)
    result = result[offset:offset+limit]

    for r in result:
        r["response_received"] = db[f"{task_name}_tres"].count_documents(
            {"scan_config.scan_id": r["_id"], "task_config.task_state": "RESPONSE_RECEIVED"}
        )
        r["scan_tags"] = [t["tag_name"] for t in db["scan_tags"].find({"scan_ids": r["_id"]})]

    return {"success": True, "error": None, "data": {"total": total, "result": result}}


@bp_scans.delete("/<task_name>")
@bp_scans.auth_required(admin_auth)
@bp_scans.input({
    "scan_id": String(required=True)
}, location="query")
def delete_scan(task_name, query_data):
    db = current_app.config["db"]
    objstore = current_app.config["objstore"]
    scan_id = query_data["scan_id"]

    # delete objstore
    for tres in db[f"{task_name}_tres"].find({"scan_config.scan_id": scan_id}):
        for item in find_sibling_data(tres, "type", "reference", sibling_key="data"):
            bucket_name = item.get("bucket_name")
            object_name = item.get("object_name")
            if bucket_name and object_name:
                objstore.remove_object(bucket_name, object_name)

    # delete tres
    db[f"{task_name}_tres"].delete_many({"scan_config.scan_id": scan_id})

    return {"success": True, "error": None, "data": None}


@bp_scans.get("/<task_name>/ids")
def get_scan_ids(task_name):
    db = current_app.config["db"]
    result = db[f"{task_name}_tres"].distinct("scan_config.scan_id")
    return {"success": True, "error": None, "data": result}


@bp_scans.post("/<task_name>/rescan")
@bp_scans.auth_required(admin_auth)
@bp_scans.input({
    "scan_id": String(required=True)
}, location="query")
def rescan_tasks_with_errors(task_name, query_data):
    db = current_app.config["db"]
    rabbit = current_app.config["rabbit"]
    scan_id = query_data["scan_id"]

    result = []
    for c in db[f"{task_name}_tres"].find({"scan_config.scan_id": scan_id, f"{task_name}_result.error": {"$exists": True}}):
        tid = c["task_config"]["task_id"]
        treq = {
            "task_config": {
                **c["task_config"],
                "task_state": "REQUEST_SENT",
                "task_timestamp_request_sent": time(),
                "task_timestamp_request_received": 0,
                "task_timestamp_response_sent": 0,
                "task_timestamp_response_received": 0
            },
            "scan_config": {**c["scan_config"]},
            f"{task_name}_config": {**c[f"{task_name}_config"]}
        }
        r = rabbit.send_treq(f"{task_name}_treq", f"/api/tasks/{task_name}/tres", tid, treq)
        if r["success"]: db[f"{task_name}_tres"].delete_many({"task_config.task_id": tid})
        result.append({"task_id": tid, "reschedule": r})

    return {"success": True, "error": None, "data": result}


@bp_scans.get("/<task_name>/duplicates")
@bp_scans.input({
    "scan_id": String(required=True)
}, location="query")
def get_duplicate_tasks_in_scan(task_name, query_data):
    db = current_app.config["db"]
    scan_id = query_data["scan_id"]

    result = list(db[f"{task_name}_tres"].aggregate([
        {"$match": {"scan_config.scan_id": scan_id}},
        {"$group": {"_id": "$task_config.task_id", "count": {"$sum": 1}, "duplicates": {"$push": "$_id"}}},
        {"$match": {"_id": {"$ne": None}, "count": {"$gt": 1}}}
    ], allowDiskUse=True))
    for r in result:
        r["duplicates"] = [str(d) for d in r["duplicates"]]

    return {"success": True, "error": None, "data": result}


@bp_scans.delete("/<task_name>/duplicates")
@bp_scans.auth_required(admin_auth)
@bp_scans.input({
    "scan_id": String(required=True)
}, location="query")
def delete_duplicate_tasks_in_scan(task_name, query_data):
    db = current_app.config["db"]
    scan_id = query_data["scan_id"]

    result = list(db[f"{task_name}_tres"].aggregate([
        {"$match": {"scan_config.scan_id": scan_id}},
        {"$group": {"_id": "$task_config.task_id", "count": {"$sum": 1}, "duplicates": {"$push": "$_id"}}},
        {"$match": {"_id": {"$ne": None}, "count": {"$gt": 1}}}
    ], allowDiskUse=True))
    for r in result:
        dups = r["duplicates"][:-1] # keep the last one
        db[f"{task_name}_tres"].delete_many({"_id": {"$in": dups}})

    return {"success": True, "error": None, "data": None}
