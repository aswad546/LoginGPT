from urllib.parse import urlparse
from tldextract import extract
from apiflask import APIBlueprint
from apiflask.fields import String
from flask import current_app
from modules.queries import q, match_scan
from config.cache import cache


bp_resolve = APIBlueprint("resolve", __name__, url_prefix="/resolve")


@bp_resolve.get("/resolved_domains_and_errors")
@bp_resolve.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def resolved_domains_and_errors(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {
        "total": 0,
        "resolved": {"reachable": 0, "unreachable": 0, "exception": 0},
        "errors": {"dns": 0, "timeout": 0, "statuscode": 0, "reset": 0, "pagecrash": 0, "emptyresponse": 0, "addressunreachable": 0, "other": 0}
    }
    result["total"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name)})
    result["resolved"]["reachable"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name), **q["match_reachable"]})
    result["resolved"]["unreachable"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name), **q["match_unreachable"]})
    result["resolved"]["exception"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name), **q["match_exception"]})
    for c in db["landscape_analysis_tres"].find({**match_scan(db, scan_id, tag_name), **q["match_resolve_error"]}):
        error = c["landscape_analysis_result"]["resolved"]["error"]
        error_msg = c["landscape_analysis_result"]["resolved"]["error_msg"]
        if "net::ERR_NAME_NOT_RESOLVED" in error_msg:
            result["errors"]["dns"] += 1
        elif "Timeout" in error_msg:
            result["errors"]["timeout"] += 1
        elif "Status code" in error_msg:
            result["errors"]["statuscode"] += 1
        elif "net::ERR_CONNECTION_RESET" in error:
            result["errors"]["reset"] += 1
        elif "Navigation failed because page crashed!" in error:
            result["errors"]["pagecrash"] += 1
        elif "net::ERR_EMPTY_RESPONSE" in error_msg:
            result["errors"]["emptyresponse"] += 1
        elif "net::ERR_ADDRESS_UNREACHABLE" in error_msg:
            result["errors"]["addressunreachable"] += 1
        else:
            result["errors"]["other"] += 1

    return {"success": True, "error": None, "data": result}


@bp_resolve.get("/resolved_domain_vs_list_domain")
@bp_resolve.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def resolved_domain_vs_list_domain(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {"same_domain": 0, "same_etld1": 0, "different_domain": 0}
    pipeline = [
        {"$project": {**q["project_base"], **q["project_resolved"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_reachable"]}},
        {"$group": {**q["group_by_domain"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline, allowDiskUse=True):
        list_domain = c["_id"]
        resolved_domain = c["resolved_domain"]
        resolved_url = c["resolved_url"]
        resolved_etld1 = extract(resolved_url).registered_domain
        if list_domain == resolved_domain: result["same_domain"] += 1
        elif list_domain == resolved_etld1: result["same_etld1"] += 1
        else: result["different_domain"] += 1

    return {"success": True, "error": None, "data": result}


@bp_resolve.get("/login_page_domain_vs_list_domain")
@bp_resolve.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def login_page_domain_vs_list_domain(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {"same_domain": 0, "same_etld1": 0, "different_domain": 0}
    pipeline = [
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"], **q["project_recognized_idps_login_page_url"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        lp_url = c["landscape_analysis_result"]["recognized_idps"]["login_page_url"]
        lp_domain = urlparse(lp_url).netloc
        lp_etld1 = extract(lp_domain).registered_domain
        list_domain = c["domain"]
        list_etld1 = extract(list_domain).registered_domain
        if list_domain == lp_domain: result["same_domain"] += 1
        elif list_etld1 == lp_etld1: result["same_etld1"] += 1
        else: result["different_domain"] += 1

    return {"success": True, "error": None, "data": result}
