from flask import current_app
from apiflask import APIBlueprint
from apiflask.fields import String
from modules.queries import q, match_scan


bp_login_trace = APIBlueprint("login_trace", __name__, url_prefix="/login_trace")


@bp_login_trace.get("/")
@bp_login_trace.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
def login_trace_overview(query_data):
    db = current_app.extensions["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {}

    result["total"] = db["login_trace_analysis_tres"].count_documents({
        **match_scan(db, scan_id, tag_name)
    })
    result["idp_login_request"] = db["login_trace_analysis_tres"].count_documents({
        **match_scan(db, scan_id, tag_name), **q["match_trace_lreq"]
    })
    result["idp_login_response"] = db["login_trace_analysis_tres"].count_documents({
        **match_scan(db, scan_id, tag_name), **q["match_trace_lres"]
    })
    result["idp_login_request_no_response"] = db["login_trace_analysis_tres"].count_documents({
        **match_scan(db, scan_id, tag_name), **q["match_trace_lreq"], **q["match_trace_no_lres"]
    })
    result["idp_login_request_method"] = list(db["login_trace_analysis_tres"].aggregate([
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_trace_lreq_method"]}},
        {"$group": {**q["group_by_trace_lreq_method"]}},
        {"$project": {"_id": 0, "method": "$_id", "count": 1}}
    ]))
    result["idp_login_response_method"] = list(db["login_trace_analysis_tres"].aggregate([
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_trace_lres_method"]}},
        {"$group": {**q["group_by_trace_lres_method"]}},
        {"$project": {"_id": 0, "method": "$_id", "count": 1}}
    ]))
    result["idp_frame"] = list(db["login_trace_analysis_tres"].aggregate([
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_trace_lreq"], **q["match_trace_lres"]}},
        {"$group": {**q["group_by_trace_frame"]}},
        {"$project": {"_id": 0, "method": "$_id", "count": 1}}
    ]))
    result["idp_integration"] = list(db["login_trace_analysis_tres"].aggregate([
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_trace_lreq"], **q["match_trace_lres"]}},
        {"$group": {**q["group_by_trace_integration"]}},
        {"$project": {"_id": 0, "method": "$_id", "count": 1}}
    ]))
    result["auto_consent_log"] = list(db["login_trace_analysis_tres"].aggregate([
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_trace_auto_consent_log"]}},
        {"$unwind": {**q["unwind_auto_consent_log"]}},
        {"$group": {**q["group_by_auto_consent_log"]}},
        {"$project": {"_id": 0, "log": "$_id", "count": 1}}
    ]))

    return result
