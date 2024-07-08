from urllib.parse import urlparse
from tldextract import extract
from apiflask import APIBlueprint
from apiflask.fields import String
from flask import current_app
from modules.queries import q, match_scan
from config.cache import cache


bp_loginpage = APIBlueprint("loginpage", __name__, url_prefix="/loginpage")


@bp_loginpage.get("/candidates_by_strategy")
@bp_loginpage.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def login_page_candidates_by_strategy(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {"total": 0, "strategies": {}, "search_engines": {}}
    pipeline = [
        {"$project": {**q["project_base"], **q["project_reachable"], **q["project_login_page_candidates_metasearch"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_reachable"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        lpcs = c["landscape_analysis_result"]["login_page_candidates"]
        for lpc in lpcs:
            result["total"] += 1
            lpc_strategy = lpc["login_page_strategy"]
            if lpc_strategy not in result["strategies"]:
                result["strategies"][lpc_strategy] = 0
            result["strategies"][lpc_strategy] += 1
            if lpc_strategy == "METASEARCH":
                mses = lpc["login_page_info"]["result_engines"]
                for mse in mses:
                    if mse not in result["search_engines"]:
                        result["search_engines"][mse] = 0
                    result["search_engines"][mse] += 1

    return {"success": True, "error": None, "data": result}


@bp_loginpage.get("/confirmed_by_integration_and_strategy")
@bp_loginpage.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def confirmed_login_pages_by_integration_and_strategy(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {"all": {"total": 0, "strategies": {}, "search_engines": {}}, "api": {}, "sdk": {}}
    pipeline = [
        {"$project": {
            **q["project_base"], **q["project_login_page_candidates_metasearch"],
            **q["project_recognized_idps_login_page_url"], **q["project_idp_name_frame_integration"]
        }},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        lpcs = c["landscape_analysis_result"]["login_page_candidates"]
        for ridp in c["landscape_analysis_result"]["recognized_idps"]:
            ridp_name = ridp["idp_name"]
            ridp_integration = ridp["idp_integration"]
            ridp_lpurl = ridp["login_page_url"]
            # all
            result["all"]["total"] += 1
            for lpc in lpcs:
                if ridp_lpurl == lpc["login_page_candidate"]:
                    lps = lpc["login_page_strategy"]
                    if lps not in result["all"]["strategies"]:
                        result["all"]["strategies"][lps] = 0
                    result["all"]["strategies"][lps] += 1
                    if lps == "METASEARCH":
                        mses = lpc["login_page_info"]["result_engines"]
                        for mse in mses:
                            if mse not in result["all"]["search_engines"]:
                                result["all"]["search_engines"][mse] = 0
                            result["all"]["search_engines"][mse] += 1
            # api
            if ridp_integration == "CUSTOM":
                if ridp_name not in result["api"]:
                    result["api"][ridp_name] = {"total": 0, "strategies": {}, "search_engines": {}}
                result["api"][ridp_name]["total"] += 1
                for lpc in lpcs:
                    if ridp_lpurl == lpc["login_page_candidate"]:
                        lps = lpc["login_page_strategy"]
                        if lps not in result["api"][ridp_name]["strategies"]:
                            result["api"][ridp_name]["strategies"][lps] = 0
                        result["api"][ridp_name]["strategies"][lps] += 1
                        if lps == "METASEARCH":
                            mses = lpc["login_page_info"]["result_engines"]
                            for mse in mses:
                                if mse not in result["api"][ridp_name]["search_engines"]:
                                    result["api"][ridp_name]["search_engines"][mse] = 0
                                result["api"][ridp_name]["search_engines"][mse] += 1
            # sdk
            elif ridp_integration != "N/A":
                if ridp_integration not in result["sdk"]:
                    result["sdk"][ridp_integration] = {"total": 0, "strategies": {}, "search_engines": {}}
                result["sdk"][ridp_integration]["total"] += 1
                for lpc in lpcs:
                    if ridp_lpurl == lpc["login_page_candidate"]:
                        lps = lpc["login_page_strategy"]
                        if lps not in result["sdk"][ridp_integration]["strategies"]:
                            result["sdk"][ridp_integration]["strategies"][lps] = 0
                        result["sdk"][ridp_integration]["strategies"][lps] += 1
                        if lps == "METASEARCH":
                            mses = lpc["login_page_info"]["result_engines"]
                            for mse in mses:
                                if mse not in result["sdk"][ridp_integration]["search_engines"]:
                                    result["sdk"][ridp_integration]["search_engines"][mse] = 0
                                result["sdk"][ridp_integration]["search_engines"][mse] += 1

    return {"success": True, "error": None, "data": result}


@bp_loginpage.get("/confirmed_by_paths_and_subdomains")
@bp_loginpage.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def confirmed_login_pages_by_paths_and_subdomains(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {"paths": {}, "subdomains": {}}
    pipeline = [
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"], **q["project_recognized_idps_login_page_url"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        lp_url = c["landscape_analysis_result"]["recognized_idps"]["login_page_url"]
        lp_parsed = urlparse(lp_url)
        lp_extract = extract(lp_url)
        if lp_parsed.path not in result["paths"]:
            result["paths"][lp_parsed.path] = 0
        result["paths"][lp_parsed.path] += 1
        if lp_extract.subdomain not in result["subdomains"]:
            result["subdomains"][lp_extract.subdomain] = 0
        result["subdomains"][lp_extract.subdomain] += 1

    return {"success": True, "error": None, "data": result}


@bp_loginpage.get("confirmed_by_metasearch_info")
@bp_loginpage.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def confirmed_login_pages_by_metasearch_info(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {"result_hit": {}}
    pipeline = [
        {"$project": {
            **q["project_base"], **q["project_login_page_candidates_metasearch"],
            **q["project_recognized_idps_idp_name"], **q["project_recognized_idps_login_page_url"]
        }},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        lpcs = c["landscape_analysis_result"]["login_page_candidates"]
        lp_url = c["landscape_analysis_result"]["recognized_idps"]["login_page_url"]
        for lpc in lpcs:
            if lp_url == lpc["login_page_candidate"]:
                if lpc["login_page_strategy"] == "METASEARCH":
                    srh = lpc["login_page_info"]["result_hit"]
                    if srh not in result["result_hit"]:
                        result["result_hit"][srh] = 0
                    result["result_hit"][srh] += 1

    return {"success": True, "error": None, "data": result}
