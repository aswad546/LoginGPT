import csv
import os
import json
import time
from uuid import uuid4
from apiflask import APIBlueprint
from apiflask.fields import Integer, String, File
from apiflask.validators import OneOf
from flask import current_app
from modules.auth import admin_auth
from modules.validate import JsonString


bp_admin = APIBlueprint("admin", __name__, url_prefix="/admin")


@bp_admin.get("/top_sites_lists")
def get_top_sites_lists():
    db = current_app.config["db"]
    result = db["top_sites_lists"].distinct("id")
    return {"success": True, "error": None, "data": result}


@bp_admin.put("/top_sites_lists")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "list_id": String(required=True),
    "list_rank_index": Integer(required=True),
    "list_domain_index": Integer(required=True)
}, location="query")
@bp_admin.input({
    "list_file": File(required=True)
}, location="files", schema_name="TopSitesListFile")
def add_top_sites_list(query_data, files_data):
    db = current_app.config["db"]
    list_id = query_data["list_id"]
    list_rank_index = query_data["list_rank_index"]
    list_domain_index = query_data["list_domain_index"]
    list_file = files_data["list_file"]

    tmp_filepath = f"/tmp/{uuid4()}.csv"
    list_file.save(tmp_filepath)

    list_entries = []
    with open(tmp_filepath, "r") as f:
        reader = csv.reader(f)
        for line in reader:
            try:
                list_entries.append({
                    "id": list_id,
                    "rank": int(line[list_rank_index]),
                    "domain": line[list_domain_index]
                })
            except IndexError as e:
                return {"success": False, "error": f"Invalid top sites list file: {e}", "data": None}

    db["top_sites_lists"].delete_many({"id": list_id})
    db["top_sites_lists"].insert_many(list_entries)

    os.remove(tmp_filepath)

    return {"success": True, "error": None, "data": None}


@bp_admin.delete("/top_sites_lists")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({"list_id": String(required=True)}, location="query")
def delete_top_sites_list(query_data):
    db = current_app.config["db"]
    list_id = query_data["list_id"]
    db["top_sites_lists"].delete_many({"id": list_id})
    return {"success": True, "error": None, "data": None}


@bp_admin.post("/db_index")
@bp_admin.auth_required(admin_auth)
def create_database_index():
    db = current_app.config["db"]

    db["top_sites_lists"].create_index([("id", 1)])
    db["top_sites_lists"].create_index([("id", 1), ("domain", 1)])

    db["ground_truth"].create_index([("gt_id", 1)])

    db["landscape_analysis_tres"].create_index([("domain", 1)])
    db["landscape_analysis_tres"].create_index([("domain", 1), ("task_config.task_timestamp_response_received", 1)])
    db["landscape_analysis_tres"].create_index([("task_config.task_id", 1)])
    db["landscape_analysis_tres"].create_index([("task_config.task_state", 1)])
    db["landscape_analysis_tres"].create_index([("task_config.task_timestamp_response_received", -1)])
    db["landscape_analysis_tres"].create_index([("landscape_analysis_result.resolved.reachable", 1)])
    db["landscape_analysis_tres"].create_index([("landscape_analysis_result.recognized_idps", 1)])

    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("domain", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("task_config.task_state", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.resolved.reachable", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.resolved.error", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.recognized_idps.idp_name", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.error", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.recognized_navcreds", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("domain", 1), ("task_config.task_timestamp_response_received", 1)])
    db["landscape_analysis_tres"].create_index([("scan_config.scan_id", 1), ("landscape_analysis_result.resolved.reachable", 1), ("landscape_analysis_result.recognized_idps.idp_name", 1)])

    db["landscape_analysis_tres"].create_index([("landscape_analysis_result.recognized_idps.idp_name", 1)])
    db["landscape_analysis_tres"].create_index([
        ("domain", 1),
        ("landscape_analysis_result.recognized_idps.idp_name", 1),
        ("landscape_analysis_result.recognized_idps.idp_integration", 1),
        ("landscape_analysis_result.recognized_idps.login_page_url", 1)
    ])

    return {"success": True, "error": None, "data": None}


@bp_admin.post("/db_query")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "method": String(required=True, validate=OneOf(["find_all", "find_one", "count", "update_many"])),
    "collection": String(required=True),
    "query": String(required=True, validate=JsonString),
    "projection": String(required=True, validate=JsonString)
}, location="json", schema_name="DatabaseQuery")
def issue_database_query(json_data):
    db = current_app.config["db"]
    method = json_data["method"]
    collection = json_data["collection"]
    query = json.loads(json_data["query"])
    projection = json.loads(json_data["projection"])

    result = None
    if method == "find_all":
        result = list(db[collection].find(query, {"_id": False, **projection}))
    elif method == "find_one":
        result = db[collection].find_one(query, {"_id": False, **projection})
    elif method == "count":
        result = db[collection].count_documents(query)
    elif method == "update_many":
        result = db[collection].update_many(query, projection).modified_count

    return {"success": True, "error": None, "data": result}


@bp_admin.get("/query")
def get_stored_database_queries():
    db = current_app.config["db"]
    result = list(db["queries"].find({}, {"_id": False}))
    return {"success": True, "error": None, "data": result}


@bp_admin.put("/query")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "description": String(required=True),
    "query": String(required=True, validate=JsonString)
}, location="query")
def add_stored_database_query(query_data):
    db = current_app.config["db"]
    description = query_data["description"]
    query = json.loads(query_data["query"])
    db["queries"].insert_one({"description": description, "query": json.dumps(query)})
    return {"success": True, "error": None, "data": None}


@bp_admin.delete("/query")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "query": String(required=True)
}, location="query")
def delete_stored_database_query(query_data):
    db = current_app.config["db"]
    query = query_data["query"]
    db["queries"].delete_many({"query": query})
    return {"success": True, "error": None, "data": None}


@bp_admin.post("/ground_truth/duplicate")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "source_gt_id": String(required=True),
    "target_gt_id": String(required=True)
}, location="query")
def duplicate_ground_truth(query_data):
    db = current_app.config["db"]
    source_gt_id = query_data["source_gt_id"]
    target_gt_id = query_data["target_gt_id"]

    for c in db["ground_truth"].find({"gt_id": source_gt_id}, {"_id": False}):
        c["gt_id"] = target_gt_id
        c["timestamp"] = int(time.time())
        db["ground_truth"].insert_one(c)

    return {"success": True, "error": None, "data": None}


@bp_admin.delete("/ground_truth")
@bp_admin.auth_required(admin_auth)
@bp_admin.input({
    "gt_id": String(required=True)
}, location="query")
def delete_ground_truth(query_data):
    db = current_app.config["db"]
    gt_id = query_data["gt_id"]
    db["ground_truth"].delete_many({"gt_id": gt_id})
    return {"success": True, "error": None, "data": None}
