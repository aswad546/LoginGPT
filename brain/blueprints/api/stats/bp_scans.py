from apiflask import APIBlueprint
from apiflask.fields import String, List
from flask import current_app
from modules.queries import q, match_scan
from config.cache import cache


bp_scans = APIBlueprint("scans", __name__, url_prefix="/scans")


@bp_scans.get("/time_vs_idps")
@bp_scans.input({
    "scan_id": List(String(), required=False),
    "tag_name": List(String(), required=False)
}, location="query")
@cache.cached(query_string=True)
def time_vs_idps(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id", [])
    tag_name = query_data.get("tag_name", [])

    scan_id = set(scan_id)
    for c in db["scan_tags"].find({"tag_name": {"$in": tag_name}}):
        scan_id.update(set(c["scan_ids"]))

    result = {}
    for sid in scan_id:
        pipline = [
            {"$project": {**q["project_base"], **q["project_timings"]}},
            {"$match": {**match_scan(db, sid, None)}},
            {"$group": {"_id": None, "total_time": {"$sum": "$landscape_analysis_result.timings.total_duration_seconds"}}}
        ]
        total_time = list(db["landscape_analysis_tres"].aggregate(pipline))
        pipeline = [
            {"$project": {**q["project_base"], **q["project_recognized_idps"]}},
            {"$match": {**match_scan(db, sid, None), **q["match_idps"]}},
            {"$group": {"_id": None, "total_idps": {"$sum": {"$size": "$landscape_analysis_result.recognized_idps"}}}}
        ]
        total_idps = list(db["landscape_analysis_tres"].aggregate(pipeline))
        if total_time and total_idps:
            result[sid] = {
                "total_time": total_time[0]["total_time"],
                "total_idps": total_idps[0]["total_idps"]
            }

    return {"success": True, "error": None, "data": result}


@bp_scans.get("/unique_idps")
@bp_scans.input({
    "scan_id": List(String(), required=False),
    "tag_name": List(String(), required=False)
}, location="query")
@cache.cached(query_string=True)
def unique_idps(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id", [])
    tag_name = query_data.get("tag_name", [])

    scan_id = set(scan_id)
    for c in db["scan_tags"].find({"tag_name": {"$in": tag_name}}):
        scan_id.update(set(c["scan_ids"]))

    result = {"idp_tuples_by_scans": {}, "unique_idp_tuples_by_scans": {}}
    for sid in scan_id:
        pipeline = [
            {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"], **q["project_recognized_idps_idp_integration"]}},
            {"$match": {**match_scan(db, sid, None), **q["match_idps"]}},
            {"$unwind": {**q["unwind_idps"]}}
        ]
        total_idps = list(db["landscape_analysis_tres"].aggregate(pipeline))
        for idp in total_idps:
            domain = idp["domain"]
            idp_name = idp["landscape_analysis_result"]["recognized_idps"]["idp_name"]
            idp_integration = idp["landscape_analysis_result"]["recognized_idps"]["idp_integration"]
            if sid not in result["idp_tuples_by_scans"]:
                result["idp_tuples_by_scans"][sid] = []
            result["idp_tuples_by_scans"][sid].append((domain, idp_name, idp_integration))
    for sid, idp_tuples in result["idp_tuples_by_scans"].items():
        for t in idp_tuples:
            if not any([t in tuples for id, tuples in result["idp_tuples_by_scans"].items() if id != sid]):
                if sid not in result["unique_idp_tuples_by_scans"]:
                    result["unique_idp_tuples_by_scans"][sid] = []
                result["unique_idp_tuples_by_scans"][sid].append(t)

    return {"success": True, "error": None, "data": result}
