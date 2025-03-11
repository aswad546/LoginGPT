import json
import random
from uuid import uuid4
from copy import deepcopy
from time import time
from nested_lookup import nested_alter
from apiflask import APIBlueprint
from apiflask.fields import String, Integer, Boolean, List
from apiflask.validators import Range
from flask import request, current_app
from modules.queries import match_latest, match_archived
from modules.objstore import store_and_mutate_data
from modules.auth import admin_auth
from modules.validate import JsonString


bp_tasks = APIBlueprint("tasks", __name__, url_prefix="/tasks")


@bp_tasks.get("/")
@bp_tasks.input({
    "offset": Integer(load_default=0, validate=Range(min=0)),
    "limit": Integer(load_default=20, validate=Range(min=1, max=50)),
    "list_id": String(load_default="tranco_6Z2X", description="sort all tasks by ranking of top sites list"),
    "scan_id": String(load_default="", description="only include tasks from specific scan"),
    "gt_id": String(load_default="", description="include tasks from ground truth"),
    "tag_name": String(load_default="", description="only include tasks from scans with specific tag"),
    "filter_sp": String(load_default="", description="only include tasks for specific domain name of service provider"),
    "filter_idp": List(String(), load_default=[], description="only include tasks for specific identity provider"),
    "filter_query": String(load_default="{}", validate=JsonString, description="only include tasks matching the mongodb query"),
    "filter_latest_idps": Boolean(load_default=True, description="include tasks marked as \"latest\" into the result"),
    "filter_archived_idps": Boolean(load_default=False, description="include tasks marked as \"archived\" into the result"),
    "filter_ground_truth_idps": Boolean(load_default=False, description="include tasks from ground truth into the result")
}, location="query")
def get_tasks(query_data):
    db = current_app.config["db"]
    offset = query_data["offset"]
    limit = query_data["limit"]
    list_id = query_data["list_id"]
    scan_id = query_data["scan_id"]
    gt_id = query_data["gt_id"]
    tag_name = query_data["tag_name"]
    filter_sp = query_data["filter_sp"]
    filter_idp = query_data["filter_idp"]
    filter_query = json.loads(query_data["filter_query"])
    filter_latest_idps = query_data["filter_latest_idps"]
    filter_archived_idps = query_data["filter_archived_idps"]
    filter_ground_truth_idps = query_data["filter_ground_truth_idps"]

    # modes
    if list_id and not (scan_id or tag_name): mode = "full" # show all or matches ranked by list
    elif not list_id and filter_sp: mode = "history" # show all for specific sp
    elif (scan_id or tag_name): mode = "scan" # show all for specific scan (optionally ranked by list)
    else: return {"success": False, "error": "Could not determine mode due to missing list_id, scan_id, tag, or filter_sp", "data": None}

    # target scan ids
    target_scan_ids = set()
    if scan_id: target_scan_ids.add(scan_id)
    if tag_name:
        for t in db["scan_tags"].find({"tag_name": tag_name}):
            target_scan_ids.update(set(t["scan_ids"]))
    target_scan_ids = list(target_scan_ids)

    # all matched domains
    total = 0
    domains = set()
    if mode == "full":
        if filter_idp: # filter idps
            if filter_latest_idps: # filter latest idps
                query = {**match_latest(db), "landscape_analysis_result.recognized_idps": {"$elemMatch": {"idp_name": {"$in": filter_idp}}}}
                if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            if filter_archived_idps: # filter archived idps
                query = {**match_archived(db), "landscape_analysis_result.recognized_idps": {"$elemMatch": {"idp_name": {"$in": filter_idp}}}}
                if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            if filter_ground_truth_idps and not filter_query: # filter ground truth idps only if no query is set
                query = {"gt_id": gt_id, "idp_name": {"$in": filter_idp}}
                if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
                domains.update(db["ground_truth"].distinct("domain", query))
            total = len(domains)
        elif filter_query: # filter query
            if filter_latest_idps: # filter latest idps
                query = {**match_latest(db)}
                if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            if filter_archived_idps: # filter archived idps
                query = {**match_archived(db)}
                if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            total = len(domains)
        else: # do not filter idps or query
            query = {"id": list_id}
            if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
            total = db["top_sites_lists"].count_documents(query)
    elif mode == "history":
        query = {"domain": filter_sp}
        total = db["landscape_analysis_tres"].count_documents(query)
    elif mode == "scan":
        if filter_idp: # filter idps
            if filter_latest_idps: # filter latest idps
                query = {"scan_config.scan_id": {"$in": target_scan_ids}, "landscape_analysis_result.recognized_idps": {"$elemMatch": {"idp_name": {"$in": filter_idp}}}}
                if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            if filter_archived_idps: # filter archived idps
                scan_domains = db["landscape_analysis_tres"].distinct("domain", {"scan_config.scan_id": {"$in": target_scan_ids}})
                query = {"scan_config.scan_id": {"$nin": target_scan_ids}, "domain": {"$in": scan_domains}, "landscape_analysis_result.recognized_idps": {"$elemMatch": {"idp_name": {"$in": filter_idp}}}}
                if filter_sp: query["domain"]["$regex"] = filter_sp # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            if filter_ground_truth_idps and not filter_query: # filter ground truth idps only if no query is set
                scan_domains = db["landscape_analysis_tres"].distinct("domain", {"scan_config.scan_id": {"$in": target_scan_ids}})
                query = {"gt_id": gt_id, "domain": {"$in": scan_domains}, "idp_name": {"$in": filter_idp}}
                if filter_sp: query["domain"]["$regex"] = filter_sp # filter sps
                domains.update(db["ground_truth"].distinct("domain", query))
            total = len(domains)
        elif filter_query: # filter query
            if filter_latest_idps: # filter latest idps
                query = {"scan_config.scan_id": {"$in": target_scan_ids}}
                if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            if filter_archived_idps: # filter archived idps
                scan_domains = db["landscape_analysis_tres"].distinct("domain", {"scan_config.scan_id": {"$in": target_scan_ids}})
                query = {"scan_config.scan_id": {"$nin": target_scan_ids}, "domain": {"$in": scan_domains}}
                if filter_sp: query["domain"]["$regex"] = filter_sp # filter sps
                if filter_query: query.update(filter_query) # filter query
                domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            total = len(domains)
        else: # do not filter idps or query
            query = {"scan_config.scan_id": {"$in": target_scan_ids}}
            if filter_sp: query["domain"] = {"$regex": filter_sp} # filter sps
            domains.update(db["landscape_analysis_tres"].distinct("domain", query))
            total = len(domains)

    # offset - offset+limit matched domains
    sites = []
    if mode == "full":
        if filter_idp or filter_query: # filter idps or query
            query = {"id": list_id, "domain": {"$in": list(domains)}}
            sites = db["top_sites_lists"].find(query).sort("rank", 1).skip(offset).limit(limit)
        else: # do not filter idps or query
            if filter_sp: # filter sps
                query = {"id": list_id, "domain": {"$regex": filter_sp}}
                sites = db["top_sites_lists"].find(query).sort("rank", 1).skip(offset).limit(limit)
            else: # do not filter sps
                query = {"id": list_id, "rank": {"$gte": offset+1, "$lte": offset+limit}}
                sites = db["top_sites_lists"].find(query)
    elif mode == "history":
        query = {"domain": filter_sp}
        sites = db["landscape_analysis_tres"].find(query, {"_id": False}).skip(offset).limit(limit)
    elif mode == "scan":
        if list_id: # sort by list
            query = {"id": list_id, "domain": {"$in": list(domains)}}
            sites = db["top_sites_lists"].find(query).sort("rank", 1).skip(offset).limit(limit)
        else: # do not sort by list
            query = {"scan_config.scan_id": {"$in": target_scan_ids}, "domain": {"$in": list(domains)}}
            sites = db["landscape_analysis_tres"].find(query, {"_id": False}).skip(offset).limit(limit)

    # aggregate info to offset - offset+limit matched domains
    result = []
    for s in sites:
        r = {
            "id": s["id"] if "id" in s else None,
            "rank": s["rank"] if "rank" in s else None,
            "domain": s["domain"]
        }

        # add la tres
        la_tres = None
        if mode == "full":
            la_tres = db["landscape_analysis_tres"].find_one({"domain": r["domain"], **match_latest(db)}, {"_id": False})
        elif mode == "history":
            la_tres = s
        elif mode == "scan":
            la_tres = db["landscape_analysis_tres"].find_one({"domain": r["domain"], "scan_config.scan_id": {"$in": target_scan_ids}}, {"_id": False})
        if la_tres: r["landscape_analysis_tres"] = la_tres
        if la_tres and not mode == "history" and not filter_latest_idps:
            la_tres["landscape_analysis_result"]["recognized_idps"] = [] # remove latest / scan idps if not requested

        # add archived idps
        if filter_archived_idps and la_tres and mode != "history":
            archived_idps = {}
            latest_idps = [
                lidp["idp_name"] for lidp in la_tres.get("landscape_analysis_result", {}).get("recognized_idps", [])
            ]
            gt = db["landscape_analysis_tres"].find(
                {"domain": la_tres["domain"], **match_archived(db)},
                {"landscape_analysis_result.recognized_idps": True}
            )
            for a in gt:
                for aidp in a.get("landscape_analysis_result", {}).get("recognized_idps", []):
                    if aidp["idp_name"] not in latest_idps:
                        archived_idps[aidp["idp_name"]] = aidp
            r["archived_idps"] = list(archived_idps.values())

        # add gt idps
        if filter_ground_truth_idps and la_tres and mode != "history":
            gt = db["ground_truth"].find(
                {"gt_id": gt_id, "domain": la_tres["domain"]},
                {"_id": False}
            )
            r["ground_truth"] = list(gt)

        result.append(r)

    # sort offset - offset+limit matched domains by rank
    result.sort(key=lambda x: x["rank"] if x["rank"] else 0, reverse=False)

    return {"success": True, "error": None, "data": {"total": total, "result": list(result)}}


@bp_tasks.put("/landscape_analysis/treq")
@bp_tasks.auth_required(admin_auth)
def dispatch_landscape_analysis_task_request():
    db = current_app.config["db"]
    rabbit = current_app.config["rabbit"]
    reqdata = request.get_json()

    scan_type = reqdata["scan_config"]["scan_type"]

    # task config
    reqdata["task_config"] = {
        "task_id": "",
        "task_state": "REQUEST_SENT",
        "task_timestamp_request_sent": 0,
        "task_timestamp_request_received": 0,
        "task_timestamp_response_sent": 0,
        "task_timestamp_response_received": 0
    }

    # scan config
    reqdata["scan_config"]["scan_id"] = str(uuid4())

    # scan type: single
    if scan_type == "single":
        treq = deepcopy(reqdata)
        tid = str(uuid4())
        treq["task_config"]["task_id"] = tid
        treq["task_config"]["task_timestamp_request_sent"] = time()
        treq["domain"] = treq["scan_config"]["domain"]
        rabbit.send_treq("landscape_analysis_treq", "/api/tasks/landscape_analysis/tres", tid, treq)

    # scan type: range
    elif scan_type == "range":
        list_id = reqdata["scan_config"]["list_id"]
        offset = reqdata["scan_config"]["offset"]
        limit = reqdata["scan_config"]["limit"]
        for gt in db["top_sites_lists"].find({"id": list_id, "rank": {"$gte": offset, "$lt": offset + limit}}):
            treq = deepcopy(reqdata)
            tid = str(uuid4())
            treq["task_config"]["task_id"] = tid
            treq["task_config"]["task_timestamp_request_sent"] = time()
            treq["domain"] = gt["domain"]
            print("Lookie here", treq["domain"])
            rabbit.send_treq("landscape_analysis_treq", "/api/tasks/landscape_analysis/tres", tid, treq)

    # scan type: ground-truth
    elif scan_type == "ground-truth":
        gt_id = reqdata["scan_config"]["gt_id"]
        offset = reqdata["scan_config"]["offset"]
        limit = reqdata["scan_config"]["limit"]
        pipeline = [{
            "$match": {
                "gt_id": gt_id,
                "rank": {"$gte": offset, "$lt": offset + limit},
                "sso": True,
                "sso_error": {"$in": [False, None]},
                "login_page_url": {"$ne": None},
                "idp_name": {"$ne": None}
            }
        },{
            "$group": {
                "_id": "$domain",
                "idps": {
                    "$push": {
                        "idp_name": "$idp_name",
                        "login_page_url": "$login_page_url"
                    }
                }
            }
        }]
        for gt in db["ground_truth"].aggregate(pipeline):
            treq = deepcopy(reqdata)
            tid = str(uuid4())
            treq["task_config"]["task_id"] = tid
            treq["task_config"]["task_timestamp_request_sent"] = time()
            treq["domain"] = gt["_id"]
            treq["landscape_analysis_config"]["login_page_config"]["login_page_strategy_scope"] = ["MANUAL"]
            idps = treq["landscape_analysis_config"]["idp_config"]["idp_scope"]
            idpc = treq["landscape_analysis_config"]["idp_config"]
            lpcmsc = treq["landscape_analysis_config"]["login_page_config"]["manual_strategy_config"]
            idpc["idp_scope"] = []
            lpcmsc["login_page_candidates"] = []
            for idp in gt["idps"]:
                idp_name = idp["idp_name"]
                login_page_url = idp["login_page_url"]
                if idp_name in idps and idp_name not in idpc["idp_scope"]:
                    idpc["idp_scope"].append(idp_name)
                if idp_name in idps and login_page_url not in lpcmsc["login_page_candidates"]:
                    lpcmsc["login_page_candidates"].append(login_page_url)
            rabbit.send_treq("landscape_analysis_treq", "/api/tasks/landscape_analysis/tres", tid, treq)

    # scan type: rescan-login-pages
    elif scan_type == "rescan-login-pages":
        reference_scan_id = reqdata["scan_config"]["reference_scan_id"]
        if reference_scan_id == "latest": q = match_latest(db)
        else: q = {"scan_config.scan_id": reference_scan_id}
        for tres in db["landscape_analysis_tres"].find(q):
            treq = deepcopy(reqdata)
            tid = str(uuid4())
            treq["task_config"]["task_id"] = tid
            treq["task_config"]["task_timestamp_request_sent"] = time()
            treq["domain"] = tres["domain"]
            treq["landscape_analysis_config"]["login_page_config"]["login_page_strategy_scope"] = ["MANUAL"]
            treq["landscape_analysis_config"]["login_page_config"]["manual_strategy_config"]["login_page_candidates"] = [
                lpc["login_page_candidate"] for lpc in tres.get("landscape_analysis_result", {}).get("login_page_candidates", [])
            ]
            rabbit.send_treq("landscape_analysis_treq", "/api/tasks/landscape_analysis/tres", tid, treq)

    return {"success": True, "error": None, "data": None}


@bp_tasks.put("/login_trace_analysis/treq")
@bp_tasks.auth_required(admin_auth)
def dispatch_login_trace_analysis_task_request():
    db = current_app.config["db"]
    rabbit = current_app.config["rabbit"]
    reqdata = request.get_json()

    scan_type = reqdata["scan_config"]["scan_type"]
    idp_credentials = reqdata["login_trace_analysis_config"]["idp_credentials"]

    # filter landscape analysis tres
    if scan_type == "task":
        q = {"task_config.task_id": reqdata["scan_config"]["target_task_id"]}
    elif scan_type == "scan":
        q = {"scan_config.scan_id": reqdata["scan_config"]["target_scan_id"]}
    elif scan_type == "tag":
        tag = db["scan_tags"].find_one({"tag_name": reqdata["scan_config"]["target_tag_name"]})
        q = {"scan_config.scan_id": {"$in": tag["scan_ids"] if tag else []}}
    idp_scope = [i["idp_name"] for i in idp_credentials]
    q = {**q, "landscape_analysis_result.recognized_idps": {"$elemMatch": {"idp_name": {"$in": idp_scope}}}}

    # create login trace analysis treq
    sid = str(uuid4())
    for c in db["landscape_analysis_tres"].find(q):
        for idp in [i for i in c["landscape_analysis_result"]["recognized_idps"] if i["idp_name"] in idp_scope]:
            tid = str(uuid4())
            idp_credential = random.choice([i for i in idp_credentials if i["idp_name"] == idp["idp_name"]])
            treq = {
                "task_config": {
                    "task_id": tid,
                    "task_state": "REQUEST_SENT",
                    "task_timestamp_request_sent": time(),
                    "task_timestamp_request_received": 0,
                    "task_timestamp_response_sent": 0,
                    "task_timestamp_response_received": 0
                },
                "scan_config": {**reqdata["scan_config"], "scan_id": sid},
                "domain": c["domain"],
                "login_trace_analysis_config": {
                    "landscape_analysis_task_id": c["task_config"]["task_id"],
                    "browser_config": c["landscape_analysis_config"]["browser_config"],
                    "idp_name": idp["idp_name"],
                    "idp_integration": idp["idp_integration"],
                    "login_page_url": idp["login_page_url"],
                    "element_coordinates_x": idp.get("element_coordinates_x"),
                    "element_coordinates_y": idp.get("element_coordinates_y"),
                    "element_width": idp.get("element_width"),
                    "element_height": idp.get("element_height"),
                    "idp_username": idp_credential["idp_username"],
                    "idp_password": idp_credential["idp_password"],
                    "idp_cookie_store": idp_credential["idp_cookie_store"]
                }
            }
            rabbit.send_treq("login_trace_analysis_treq", "/api/tasks/login_trace_analysis/tres", tid, treq)

    return {"success": True, "error": None, "data": None}


@bp_tasks.put("/wildcard_receiver_analysis/treq")
@bp_tasks.auth_required(admin_auth)
def dispatch_wildcard_receiver_analysis_task_request():
    db = current_app.config["db"]
    rabbit = current_app.config["rabbit"]
    reqdata = request.get_json()

    scan_type = reqdata["scan_config"]["scan_type"]
    idp_credentials = reqdata["wildcard_receiver_analysis_config"]["idp_credentials"]

    # filter landscape analysis tres
    if scan_type == "task":
        q = {"task_config.task_id": reqdata["scan_config"]["target_task_id"]}
    elif scan_type == "scan":
        q = {"scan_config.scan_id": reqdata["scan_config"]["target_scan_id"]}
    elif scan_type == "tag":
        tag = db["scan_tags"].find_one({"tag_name": reqdata["scan_config"]["target_tag_name"]})
        q = {"scan_config.scan_id": {"$in": tag["scan_ids"] if tag else []}}
    idp_scope = [i["idp_name"] for i in idp_credentials]
    q = {**q, "landscape_analysis_result.recognized_idps": {"$elemMatch": {"idp_name": {"$in": idp_scope}, "idp_integration": "CUSTOM", "idp_frame": "POPUP"}}}

    # create wildcard receiver analysis treq
    sid = str(uuid4())
    for c in db["landscape_analysis_tres"].find(q):
        for idp in [
            i for i in c["landscape_analysis_result"]["recognized_idps"]
            if i["idp_name"] in idp_scope and i["idp_integration"] == "CUSTOM" and i["idp_frame"] == "POPUP"
        ]:
            tid = str(uuid4())
            idp_credential = random.choice([i for i in idp_credentials if i["idp_name"] == idp["idp_name"]])
            treq = {
                "task_config": {
                    "task_id": tid,
                    "task_state": "REQUEST_SENT",
                    "task_timestamp_request_sent": time(),
                    "task_timestamp_request_received": 0,
                    "task_timestamp_response_sent": 0,
                    "task_timestamp_response_received": 0
                },
                "scan_config": {**reqdata["scan_config"], "scan_id": sid},
                "domain": c["domain"],
                "wildcard_receiver_analysis_config": {
                    "landscape_analysis_task_id": c["task_config"]["task_id"],
                    "browser_config": c["landscape_analysis_config"]["browser_config"],
                    "idp_name": idp["idp_name"],
                    "idp_integration": idp["idp_integration"],
                    "login_page_url": idp["login_page_url"],
                    "element_coordinates_x": idp.get("element_coordinates_x"),
                    "element_coordinates_y": idp.get("element_coordinates_y"),
                    "element_width": idp.get("element_width"),
                    "element_height": idp.get("element_height"),
                    "idp_username": idp_credential["idp_username"],
                    "idp_password": idp_credential["idp_password"],
                    "idp_cookie_store": idp_credential["idp_cookie_store"]
                }
            }
            rabbit.send_treq("wildcard_receiver_analysis_treq", "/api/tasks/wildcard_receiver_analysis/tres", tid, treq)

    return {"success": True, "error": None, "data": None}


@bp_tasks.put("/<task_name>/tres")
@bp_tasks.auth_required(admin_auth)
def store_task_response(task_name):
    db = current_app.config["db"]
    objstore = current_app.config["objstore"]
    reqdata = request.get_json()

    # task state
    reqdata["task_config"]["task_state"] = "RESPONSE_RECEIVED"
    reqdata["task_config"]["task_timestamp_response_received"] = time()

    # objstore
    cb = lambda bucket_name, data, ext: store_and_mutate_data(
        objstore, bucket_name, reqdata["domain"], data, ext
    )
    nested_alter(reqdata, "login_page_candidate_screenshot", lambda d: cb("login-page-candidate-screenshot", d, "png"), in_place=True)
    nested_alter(reqdata, "idp_screenshot", lambda d: cb("idp-screenshot", d, "png"), in_place=True)
    nested_alter(reqdata, "keyword_recognition_screenshot", lambda d: cb("keyword-recognition-screenshot", d, "png"), in_place=True)
    nested_alter(reqdata, "logo_recognition_screenshot", lambda d: cb("logo-recognition-screenshot", d, "png"), in_place=True)
    nested_alter(reqdata, "idp_har", lambda d: cb("idp-har", d, "har"), in_place=True)
    nested_alter(reqdata, "login_page_analysis_har", lambda d: cb("login-page-analysis-har", d, "har"), in_place=True)
    nested_alter(reqdata, "element_tree_markup", lambda d: cb("element-tree-markup", d, "json"), in_place=True)
    nested_alter(reqdata, "metadata_data", lambda d: cb("metadata-data", d, "json"), in_place=True)
    nested_alter(reqdata, "sitemap", lambda d: cb("sitemap", d, "json"), in_place=True)
    nested_alter(reqdata, "robots", lambda d: cb("robots", d, "json"), in_place=True)
    nested_alter(reqdata, "login_trace_screenshot", lambda d: cb("login-trace-screenshot", d, "png"), in_place=True)
    nested_alter(reqdata, "login_trace_har", lambda d: cb("login-trace-har", d, "har"), in_place=True)
    nested_alter(reqdata, "login_trace_storage_state", lambda d: cb("login-trace-storage-state", d, "json"), in_place=True)

    # db
    db[f"{task_name}_tres"].insert_one(reqdata)

    return {"success": True, "error": None, "data": None}
