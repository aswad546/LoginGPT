from math import ceil
from apiflask import APIBlueprint
from apiflask.fields import String
from flask import current_app
from modules.queries import q, match_scan
from config.cache import cache


bp_sso = APIBlueprint("sso", __name__, url_prefix="/sso")


@bp_sso.get("/")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_support(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {}
    result["domains_all"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name)})
    result["domains_with_sso"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name), **q["match_idp_name"]})
    result["domains_without_sso"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name), **q["match_reachable"], **q["match_no_idp_name"]})
    result["domains_not_reachable"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name), **q["match_unreachable"]})
    result["domains_with_other_errors"] = db["landscape_analysis_tres"].count_documents({**match_scan(db, scan_id, tag_name), **q["match_exception"]})
    result["buttons_all"] = next(db["landscape_analysis_tres"].aggregate([
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}},
        {"$count": "count"}
    ]), {}).get("count", 0)

    return {"success": True, "error": None, "data": result}


@bp_sso.get("/idp")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_idp(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {}
    result["buttons_idps"] = {c["_id"]: c["count"] for c in db["landscape_analysis_tres"].aggregate([
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}},
        {"$group": {"_id": "$landscape_analysis_result.recognized_idps.idp_name", "count": {"$sum": 1}}}
    ])}
    result["domains_idps"] = {c["_id"]: c["count"] for c in db["landscape_analysis_tres"].aggregate([
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}},
        {"$group": {"_id": "$landscape_analysis_result.recognized_idps.idp_name", "domains": {"$addToSet": "$domain"}}},
        {"$addFields": {"count": {"$size": "$domains"}}}
    ])}

    return {"success": True, "error": None, "data": result}


@bp_sso.get("/rank")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False),
    "list_id": String(load_default="tranco_6Z2X")
}, location="query")
@cache.cached(query_string=True)
def sso_by_rank(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")
    list_id = query_data["list_id"]

    list_all = db["top_sites_lists"].count_documents({"id": list_id})
    buttons_all = [(c["domain"], c["rank"]) for c in db["landscape_analysis_tres"].aggregate([
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}},
        {"$lookup": {"from": "top_sites_lists", "localField": "domain", "foreignField": "domain", "as": "top_sites_lists"}},
        {"$unwind": {"path": "$top_sites_lists", "preserveNullAndEmptyArrays": False}},
        {"$match": {"top_sites_lists.id": list_id}},
        {"$addFields": {"rank": "$top_sites_lists.rank"}}
    ])]

    result = {}
    range = int(list_all / 50)
    for domain, rank in buttons_all:
        marker = ceil(int(rank) / float(range)) * range
        key = f"{marker-range}"
        if key not in result:
            result[key] = []
        result[key].append(domain)

    return {"success": True, "error": None, "data": {
        "buttons_by_rank": {k: len(v) for k, v in result.items()},
        "domains_with_sso_by_rank": {k: len(set(v)) for k, v in result.items()}
    }}


@bp_sso.get("/element_coordinates")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_element_coordinates(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = []
    pipeline = [
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"], **q["project_element_coordinates"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        x = c["landscape_analysis_result"]["recognized_idps"].get("element_coordinates_x")
        y = c["landscape_analysis_result"]["recognized_idps"].get("element_coordinates_y")
        w = c["landscape_analysis_result"]["recognized_idps"].get("element_width")
        h = c["landscape_analysis_result"]["recognized_idps"].get("element_height")
        if not x or not y or not w or not h: continue
        result.append({"x": x, "y": y, "w": w, "h": h})

    return {"success": True, "error": None, "data": result}


@bp_sso.get("/element_tree")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_element_tree(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {
        "click_elements" : 0,
        "img_elements" : 0,
        "other_elements" : 0,
        "click_elements_by_tag" : {},
        "img_elements_by_tag" : {},
        "click_elements_by_recognition_strategy" : {},
        "img_elements_by_recognition_strategy" : {},
        "other_elements_by_recognition_strategy" : {}
    }
    pipeline = [
        {"$project": {
            **q["project_base"], **q["project_recognized_idps_idp_name"],
            **q["project_recognized_idps_element_tree"], **q["project_recognized_idps_recognition_strategy"]
        }},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"], **q["match_element_tree"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        element_tree = c["landscape_analysis_result"]["recognized_idps"]["element_tree"]
        recognition_strategy = c["landscape_analysis_result"]["recognized_idps"]["recognition_strategy"]
        # check click elements (i.e., button, ...)
        click_element_in_element_tree = False
        for e in ["BUTTON", "A", "INPUT"]:
            if e in element_tree:
                click_element_in_element_tree = True
                if e not in result["click_elements_by_tag"]:
                    result["click_elements_by_tag"][e] = 0
                result["click_elements_by_tag"][e] += 1
                if recognition_strategy not in result["click_elements_by_recognition_strategy"]:
                    result["click_elements_by_recognition_strategy"][recognition_strategy] = {}
                if e not in result["click_elements_by_recognition_strategy"][recognition_strategy]:
                    result["click_elements_by_recognition_strategy"][recognition_strategy][e] = 0
                result["click_elements_by_recognition_strategy"][recognition_strategy][e] += 1
        # check img elements (i.e., img, ...)
        img_element_in_element_tree = False
        for e in ["IMG", "svg", "CANVAS", "OBJECT", "PICTURE"]:
            if e in element_tree:
                img_element_in_element_tree = True
                if e not in result["img_elements_by_tag"]:
                    result["img_elements_by_tag"][e] = 0
                result["img_elements_by_tag"][e] += 1
                if recognition_strategy not in result["img_elements_by_recognition_strategy"]:
                    result["img_elements_by_recognition_strategy"][recognition_strategy] = {}
                if e not in result["img_elements_by_recognition_strategy"][recognition_strategy]:
                    result["img_elements_by_recognition_strategy"][recognition_strategy][e] = 0
                result["img_elements_by_recognition_strategy"][recognition_strategy][e] += 1
        # sum click and img elements
        if click_element_in_element_tree:
            result["click_elements"] += 1
        if img_element_in_element_tree:
            result["img_elements"] += 1
        # other elements
        if not click_element_in_element_tree and not img_element_in_element_tree:
            result["other_elements"] += 1
            if recognition_strategy not in result["other_elements_by_recognition_strategy"]:
                result["other_elements_by_recognition_strategy"][recognition_strategy] = 0
            result["other_elements_by_recognition_strategy"][recognition_strategy] += 1

    return {"success": True, "error": None, "data": result}


@bp_sso.get("/integration")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_integration(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {
        "buttons_custom": {},
        "buttons_sdks": {},
        "buttons_flows": {},
        "buttons_integrations": {"CUSTOM": [], "SDK": []}
    }
    pipeline = [
        {"$project": {**q["project_base"], **q["project_idp_name_frame_integration"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        idp_name = c["landscape_analysis_result"]["recognized_idps"]["idp_name"]
        idp_frame = c["landscape_analysis_result"]["recognized_idps"]["idp_frame"]
        idp_integration = c["landscape_analysis_result"]["recognized_idps"]["idp_integration"]
        # custom integration
        if idp_integration == "CUSTOM":
            result["buttons_integrations"]["CUSTOM"].append(c["domain"])
            if idp_name not in result["buttons_custom"]:
                result["buttons_custom"][idp_name] = []
            result["buttons_custom"][idp_name].append(c["domain"])
            if idp_frame:
                if f"CUSTOM_{idp_frame}" not in result["buttons_flows"]:
                    result["buttons_flows"][f"CUSTOM_{idp_frame}"] = []
                result["buttons_flows"][f"CUSTOM_{idp_frame}"].append(c["domain"])
        # sdk integration
        elif idp_integration != "N/A":
            result["buttons_integrations"]["SDK"].append(c["domain"])
            if idp_integration not in result["buttons_sdks"]:
                result["buttons_sdks"][idp_integration] = []
            result["buttons_sdks"][idp_integration].append(c["domain"])
            if idp_frame:
                if f"SDK_{idp_frame}" not in result["buttons_flows"]:
                    result["buttons_flows"][f"SDK_{idp_frame}"] = []
                result["buttons_flows"][f"SDK_{idp_frame}"].append(c["domain"])

    return {"success": True, "error": None, "data": {
        "buttons_custom": {k: len(v) for k, v in result["buttons_custom"].items()},
        "domains_custom": {k: len(set(v)) for k, v in result["buttons_custom"].items()},
        "buttons_sdks": {k: len(v) for k, v in result["buttons_sdks"].items()},
        "domains_sdks": {k: len(set(v)) for k, v in result["buttons_sdks"].items()},
        "buttons_flows": {k: len(v) for k, v in result["buttons_flows"].items()},
        "domains_flows": {k: len(set(v)) for k, v in result["buttons_flows"].items()},
        "buttons_integrations": {k: len(v) for k, v in result["buttons_integrations"].items()},
        "domains_integrations": {k: len(set(v)) for k, v in result["buttons_integrations"].items()},
    }}


@bp_sso.get("/frame")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_frame(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {
        "buttons_frames": {},
        "buttons_custom_frames": {},
        "buttons_sdk_frames": {},
        "buttons_frames_by_custom": {},
        "buttons_frames_by_sdk": {}
    }
    pipeline = [
        {"$project": {**q["project_base"], **q["project_idp_name_frame_integration"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        idp_name = c["landscape_analysis_result"]["recognized_idps"]["idp_name"]
        idp_frame = c["landscape_analysis_result"]["recognized_idps"]["idp_frame"]
        idp_integration = c["landscape_analysis_result"]["recognized_idps"]["idp_integration"]
        # frame
        if idp_frame not in result["buttons_frames"]:
            result["buttons_frames"][idp_frame] = []
        result["buttons_frames"][idp_frame].append(c["domain"])
        # custom integration
        if idp_integration == "CUSTOM":
            if idp_frame not in result["buttons_custom_frames"]:
                result["buttons_custom_frames"][idp_frame] = []
            result["buttons_custom_frames"][idp_frame].append(c["domain"])
            if idp_name not in result["buttons_frames_by_custom"]:
                result["buttons_frames_by_custom"][idp_name] = {}
            if idp_frame not in result["buttons_frames_by_custom"][idp_name]:
                result["buttons_frames_by_custom"][idp_name][idp_frame] = []
            result["buttons_frames_by_custom"][idp_name][idp_frame].append(c["domain"])
        # sdk integration
        elif idp_integration != "N/A":
            if idp_frame not in result["buttons_sdk_frames"]:
                result["buttons_sdk_frames"][idp_frame] = []
            result["buttons_sdk_frames"][idp_frame].append(c["domain"])
            if idp_integration not in result["buttons_frames_by_sdk"]:
                result["buttons_frames_by_sdk"][idp_integration] = {}
            if idp_frame not in result["buttons_frames_by_sdk"][idp_integration]:
                result["buttons_frames_by_sdk"][idp_integration][idp_frame] = []
            result["buttons_frames_by_sdk"][idp_integration][idp_frame].append(c["domain"])

    return {"success": True, "error": None, "data": {
        "buttons_frames": {k: len(v) for k, v in result["buttons_frames"].items()},
        "domains_frames": {k: len(set(v)) for k, v in result["buttons_frames"].items()},
        "buttons_custom_frames": {k: len(v) for k, v in result["buttons_custom_frames"].items()},
        "domains_custom_frames": {k: len(set(v)) for k, v in result["buttons_custom_frames"].items()},
        "buttons_sdk_frames": {k: len(v) for k, v in result["buttons_sdk_frames"].items()},
        "domains_sdk_frames": {k: len(set(v)) for k, v in result["buttons_sdk_frames"].items()},
        "buttons_frames_by_custom": {k: {k2: len(v2) for k2, v2 in v.items()} for k, v in result["buttons_frames_by_custom"].items()},
        "domains_frames_by_custom": {k: {k2: len(set(v2)) for k2, v2 in v.items()} for k, v in result["buttons_frames_by_custom"].items()},
        "buttons_frames_by_sdk": {k: {k2: len(v2) for k2, v2 in v.items()} for k, v in result["buttons_frames_by_sdk"].items()},
        "domains_frames_by_sdk": {k: {k2: len(set(v2)) for k2, v2 in v.items()} for k, v in result["buttons_frames_by_sdk"].items()}
    }}


@bp_sso.get("/recognition_strategy")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_recognition_strategy(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {
        "buttons_recognition_strategy" : {},
        "buttons_custom_recognition_strategy" : {},
        "buttons_sdk_recognition_strategy" : {},
        "buttons_recognition_strategy_by_custom" : {},
        "buttons_recognition_strategy_by_sdk" : {}
    }
    pipeline = [
        {"$project": {**q["project_base"], **q["project_idp_name_frame_integration"], **q["project_recognized_idps_recognition_strategy"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        idp_name = c["landscape_analysis_result"]["recognized_idps"]["idp_name"]
        idp_integration = c["landscape_analysis_result"]["recognized_idps"]["idp_integration"]
        idp_recognition_strategy = c["landscape_analysis_result"]["recognized_idps"]["recognition_strategy"]
        # recognition strategy
        if idp_recognition_strategy not in result["buttons_recognition_strategy"]:
            result["buttons_recognition_strategy"][idp_recognition_strategy] = []
        result["buttons_recognition_strategy"][idp_recognition_strategy].append(c["domain"])
        # custom integration
        if idp_integration == "CUSTOM":
            if idp_recognition_strategy not in result["buttons_custom_recognition_strategy"]:
                result["buttons_custom_recognition_strategy"][idp_recognition_strategy] = []
            result["buttons_custom_recognition_strategy"][idp_recognition_strategy].append(c["domain"])
            if idp_name not in result["buttons_recognition_strategy_by_custom"]:
                result["buttons_recognition_strategy_by_custom"][idp_name] = {}
            if idp_recognition_strategy not in result["buttons_recognition_strategy_by_custom"][idp_name]:
                result["buttons_recognition_strategy_by_custom"][idp_name][idp_recognition_strategy] = []
            result["buttons_recognition_strategy_by_custom"][idp_name][idp_recognition_strategy].append(c["domain"])
        # sdk integration
        elif idp_integration != "N/A":
            if idp_recognition_strategy not in result["buttons_sdk_recognition_strategy"]:
                result["buttons_sdk_recognition_strategy"][idp_recognition_strategy] = []
            result["buttons_sdk_recognition_strategy"][idp_recognition_strategy].append(c["domain"])
            if idp_integration not in result["buttons_recognition_strategy_by_sdk"]:
                result["buttons_recognition_strategy_by_sdk"][idp_integration] = {}
            if idp_recognition_strategy not in result["buttons_recognition_strategy_by_sdk"][idp_integration]:
                result["buttons_recognition_strategy_by_sdk"][idp_integration][idp_recognition_strategy] = []
            result["buttons_recognition_strategy_by_sdk"][idp_integration][idp_recognition_strategy].append(c["domain"])

    return {"success": True, "error": None, "data": {
        "buttons_recognition_strategy": {k: len(v) for k, v in result["buttons_recognition_strategy"].items()},
        "domains_recognition_strategy": {k: len(set(v)) for k, v in result["buttons_recognition_strategy"].items()},
        "buttons_custom_recognition_strategy": {k: len(v) for k, v in result["buttons_custom_recognition_strategy"].items()},
        "domains_custom_recognition_strategy": {k: len(set(v)) for k, v in result["buttons_custom_recognition_strategy"].items()},
        "buttons_sdk_recognition_strategy": {k: len(v) for k, v in result["buttons_sdk_recognition_strategy"].items()},
        "domains_sdk_recognition_strategy": {k: len(set(v)) for k, v in result["buttons_sdk_recognition_strategy"].items()},
        "buttons_recognition_strategy_by_custom": {k: {k2: len(v2) for k2, v2 in v.items()} for k, v in result["buttons_recognition_strategy_by_custom"].items()},
        "domains_recognition_strategy_by_custom": {k: {k2: len(set(v2)) for k2, v2 in v.items()} for k, v in result["buttons_recognition_strategy_by_custom"].items()},
        "buttons_recognition_strategy_by_sdk": {k: {k2: len(v2) for k2, v2 in v.items()} for k, v in result["buttons_recognition_strategy_by_sdk"].items()},
        "domains_recognition_strategy_by_sdk": {k: {k2: len(set(v2)) for k2, v2 in v.items()} for k, v in result["buttons_recognition_strategy_by_sdk"].items()}
    }}


@bp_sso.get("/keyword")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_keyword(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {
        "element_validity": {},
        "keyword_recognition_candidates": {},
        "keyword_recognition_hit_number_clicks": {}
    }
    pipeline = [
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"], **q["project_idp_keyword_recognition"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}},
        {"$match": {**q["match_keyword_recognition"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        ridp = c["landscape_analysis_result"]["recognized_idps"]
        ev = ridp.get("element_validity")
        krc = ridp["keyword_recognition_candidates"]
        krhnc = ridp["keyword_recognition_hit_number_clicks"]
        if ev is None: continue
        # element validity
        if ev not in result["element_validity"]:
            result["element_validity"][ev] = []
        result["element_validity"][ev].append(c["domain"])
        # keyword recognition candidates
        if krc not in result["keyword_recognition_candidates"]:
            result["keyword_recognition_candidates"][krc] = []
        result["keyword_recognition_candidates"][krc].append(c["domain"])
        # keyword recognition hit number clicks
        if krhnc not in result["keyword_recognition_hit_number_clicks"]:
            result["keyword_recognition_hit_number_clicks"][krhnc] = []
        result["keyword_recognition_hit_number_clicks"][krhnc].append(c["domain"])

    return {"success": True, "error": None, "data": {
        "buttons_element_validity": {k: len(v) for k, v in result["element_validity"].items()},
        "domains_element_validity": {k: len(set(v)) for k, v in result["element_validity"].items()},
        "buttons_keyword_recognition_candidates": {k: len(v) for k, v in result["keyword_recognition_candidates"].items()},
        "domains_keyword_recognition_candidates": {k: len(set(v)) for k, v in result["keyword_recognition_candidates"].items()},
        "buttons_keyword_recognition_hit_number_clicks": {k: len(v) for k, v in result["keyword_recognition_hit_number_clicks"].items()},
        "domains_keyword_recognition_hit_number_clicks": {k: len(set(v)) for k, v in result["keyword_recognition_hit_number_clicks"].items()}
    }}


@bp_sso.get("/logo")
@bp_sso.input({
    "scan_id": String(required=False),
    "tag_name": String(required=False)
}, location="query")
@cache.cached(query_string=True)
def sso_by_logo(query_data):
    db = current_app.config["db"]
    scan_id = query_data.get("scan_id")
    tag_name = query_data.get("tag_name")

    result = {
        "template_filenames": {},
        "template_scales": {"scales": [], "min": 0, "max": 0, "avg": 0, "by_template_filename": {}},
        "matching_scores": {"scores": [], "min": 0, "max": 0, "avg": 0, "by_template_filename": {}},
    }
    pipeline = [
        {"$project": {**q["project_base"], **q["project_recognized_idps_idp_name"], **q["project_idp_logo_recognition"]}},
        {"$match": {**match_scan(db, scan_id, tag_name), **q["match_idp_name"]}},
        {"$unwind": {**q["unwind_idps"]}},
        {"$match": {**q["match_logo_recognition"]}}
    ]
    for c in db["landscape_analysis_tres"].aggregate(pipeline):
        ridp = c["landscape_analysis_result"]["recognized_idps"]
        template_filename = ridp["logo_recognition_template_filename"]
        template_scale = ridp["logo_recognition_template_scale"]
        matching_score = ridp["logo_recognition_matching_score"]
        # template filename
        if template_filename not in result["template_filenames"]:
            result["template_filenames"][template_filename] = []
        result["template_filenames"][template_filename].append(c["domain"])
        # template scale by template filename
        if template_filename not in result["template_scales"]["by_template_filename"]:
            result["template_scales"]["by_template_filename"][template_filename] = []
        result["template_scales"]["by_template_filename"][template_filename].append(template_scale)
        result["template_scales"]["scales"].append(template_scale)
        # matching score by template filename
        if template_filename not in result["matching_scores"]["by_template_filename"]:
            result["matching_scores"]["by_template_filename"][template_filename] = []
        result["matching_scores"]["by_template_filename"][template_filename].append(matching_score)
        result["matching_scores"]["scores"].append(matching_score)
    # template scales
    result["template_scales"]["min"] = min(result["template_scales"]["scales"])
    result["template_scales"]["max"] = max(result["template_scales"]["scales"])
    result["template_scales"]["avg"] = sum(result["template_scales"]["scales"]) / len(result["template_scales"]["scales"])
    # matching scores
    result["matching_scores"]["min"] = min(result["matching_scores"]["scores"])
    result["matching_scores"]["max"] = max(result["matching_scores"]["scores"])
    result["matching_scores"]["avg"] = sum(result["matching_scores"]["scores"]) / len(result["matching_scores"]["scores"])

    return {"success": True, "error": None, "data": result}
