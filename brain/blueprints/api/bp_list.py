import json
import requests
from tranco import Tranco
from apiflask import APIBlueprint
from apiflask.fields import Date, Integer
from apiflask.validators import Range
from flask import current_app


bp_list = APIBlueprint("list", __name__, url_prefix="/list")
tranco = Tranco(cache=True, cache_dir="/tmp/tranco")


@bp_list.get("/")
@bp_list.input({
    "date": Date(required=True, description="date of the list (YYYY-MM-DD)"),
    "start_rank": Integer(load_default=1, validate=Range(min=1, max=1_000_000), description="rank of first entry to fetch from the list"),
    "end_rank": Integer(load_default=1_000_000, validate=Range(min=1, max=1_000_000), description="rank of last entry to fetch from the list")
}, location="query")
def get_list(query_data):
    db = current_app.config["db"]
    date = query_data["date"]
    start_rank = query_data["start_rank"]
    end_rank = query_data["end_rank"]

    # timestamp
    ts = int(date.strftime("%s"))

    # load tranco list
    try:
        tranco_list = tranco.list(date=date)
    except AttributeError as e:
        return {"success": False, "error": f"{e}", "data": None}

    # only include tasks in the list from scans with special tag
    list_scan_ids = []
    c = db["scan_tags"].find_one({"tag_name": "sso-tranco-list"})
    if c: list_scan_ids = c["scan_ids"]

    # load sso list
    def generate():
        yield "["
        for rank, domain in enumerate(tranco_list.list[start_rank-1:end_rank]):
            pipeline = [
                {"$match": {"domain": domain, "scan_config.scan_id": {"$in": list_scan_ids}, "task_config.task_timestamp_response_received": {"$lte": ts}}},
                {"$sort": {"task_config.task_timestamp_response_received": -1}},
                {"$limit": 1}
            ]
            e = {"rank": rank+1, "domain": domain}
            c = list(db["landscape_analysis_tres"].aggregate(pipeline))
            if c:
                e["task_id"] = c[0]["task_config"].get("task_id")
                e["task_timestamp_response_received"] = c[0]["task_config"].get("task_timestamp_response_received")
                e["resolved"] = c[0]["landscape_analysis_result"].get("resolved")
                e["timings"] = c[0]["landscape_analysis_result"].get("timings")
                e["login_page_candidates"] = c[0]["landscape_analysis_result"].get("login_page_candidates")
                e["recognized_idps"] = c[0]["landscape_analysis_result"].get("recognized_idps")
                e["recognized_lastpass_icons"] = c[0]["landscape_analysis_result"].get("recognized_lastpass_icons")
                e["recognized_navcreds"] = c[0]["landscape_analysis_result"].get("recognized_navcreds")
                e["metadata_available"] = c[0]["landscape_analysis_result"].get("metadata_available")
                e["metadata_data"] = c[0]["landscape_analysis_result"].get("metadata_data")
            yield f"{json.dumps(e)}"
            if rank != end_rank-1: yield f", "
        yield "]"

    return generate(), {
        "Content-Type": "application/json",
        "Content-Disposition": f"attachment; filename=sso_{date}_tranco_{tranco_list.list_id}.json"
    }


@bp_list.get("/tranco_id")
@bp_list.input({
    "date": Date(required=True, description="date of the list (YYYY-MM-DD)")
}, location="query")
def get_tranco_id(query_data):
    date = query_data["date"]
    try:
        r = requests.get(f"https://tranco-list.eu/daily_list?date={date}", allow_redirects=False)
        print(r)
        l = r.headers["Location"]
        if len(l.split("/")) >= 3:
            tranco_id = l.split("/")[2]
        else:
            tranco_id = None
        return {"success": True, "error": None, "data": tranco_id}
    except Exception as e:
        return {"success": False, "error": f"{e}", "data": None}
