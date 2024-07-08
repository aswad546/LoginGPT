q = {
    #### matches ####
    "match_idps": {"landscape_analysis_result.recognized_idps": {"$exists": True, "$ne": []}},
    "match_no_idps": {"landscape_analysis_result.recognized_idps": {"$exists": True, "$eq": []}},
    "match_reachable": {"landscape_analysis_result.resolved.reachable": True},
    "match_unreachable": {"landscape_analysis_result.resolved.reachable": False},
    "match_resolve_error": {"landscape_analysis_result.resolved.error": {"$exists": True}},
    "match_exception": {"landscape_analysis_result.error": {"$exists": True}},
    "match_element_tree": {"landscape_analysis_result.recognized_idps.element_tree": {"$exists": True, "$nin": [None, []]}},
    "match_pm_leaks": {"wildcard_receiver_analysis_result.exploitation_stage.postmessage_leaks":{"$exists": True, "$ne": []}},
    "match_no_idp_name": {"landscape_analysis_result.recognized_idps.idp_name": {"$exists": False}},
    "match_idp_name": {"landscape_analysis_result.recognized_idps.idp_name": {"$exists": True}},
    "match_keyword_recognition": {"landscape_analysis_result.recognized_idps.recognition_strategy": "KEYWORD"},
    "match_logo_recognition": {"landscape_analysis_result.recognized_idps.recognition_strategy": "LOGO"},
    "match_trace_lreq": {"login_trace_analysis_result.idp_login_request": {"$ne": None}},
    "match_trace_lres": {"login_trace_analysis_result.idp_login_response": {"$ne": None}},
    "match_trace_no_lres": {"login_trace_analysis_result.idp_login_response": {"$eq": None}},
    "match_trace_lreq_method": {"login_trace_analysis_result.idp_login_request_method": {"$ne": None}},
    "match_trace_lres_method": {"login_trace_analysis_result.idp_login_response_method": {"$ne": None}},
    "match_trace_auto_consent_log": {"login_trace_analysis_result.auto_consent_log": {"$ne": []}},

    #### projections ####
    "project_base": {"domain": True, "scan_config.scan_id": True},
    "project_resolved": {"landscape_analysis_result.resolved": True},
    "project_reachable": {"landscape_analysis_result.resolved.reachable": True},
    "project_timings": {"landscape_analysis_result.timings": True},
    "project_login_page_candidates": {"landscape_analysis_result.login_page_candidates": True},
    "project_recognized_idps": {"landscape_analysis_result.recognized_idps": True},
    "project_recognized_idps_idp_name": {"landscape_analysis_result.recognized_idps.idp_name": True},
    "project_recognized_idps_idp_integration": {"landscape_analysis_result.recognized_idps.idp_integration": True},
    "project_recognized_idps_login_page_url": {"landscape_analysis_result.recognized_idps.login_page_url": True},
    "project_recognized_idps_element_tree": {"landscape_analysis_result.recognized_idps.element_tree": True},
    "project_recognized_idps_recognition_strategy": {"landscape_analysis_result.recognized_idps.recognition_strategy": True},
    "project_errors": {"landscape_analysis_result.error": True},
    "project_wra_exploitation_stage": {"wildcard_receiver_analysis_result.exploitation_stage": True},
    "project_idp_name_frame_integration": {
        "landscape_analysis_result.recognized_idps.idp_name": True,
        "landscape_analysis_result.recognized_idps.idp_frame": True,
        "landscape_analysis_result.recognized_idps.idp_integration": True
    },
    "project_element_coordinates": {
        "landscape_analysis_result.recognized_idps.element_coordinates_x": True,
        "landscape_analysis_result.recognized_idps.element_coordinates_y": True,
        "landscape_analysis_result.recognized_idps.element_width": True,
        "landscape_analysis_result.recognized_idps.element_height": True
    },
    "project_idp_keyword_recognition": {
        "landscape_analysis_result.recognized_idps.recognition_strategy": True,
        "landscape_analysis_result.recognized_idps.element_validity": True,
        "landscape_analysis_result.recognized_idps.keyword_recognition_candidates": True,
        "landscape_analysis_result.recognized_idps.keyword_recognition_hit_number_clicks": True,
    },
    "project_idp_logo_recognition": {
        "landscape_analysis_result.recognized_idps.recognition_strategy": True,
        "landscape_analysis_result.recognized_idps.logo_recognition_candidates": True,
        "landscape_analysis_result.recognized_idps.logo_recognition_hit_number_clicks": True,
        "landscape_analysis_result.recognized_idps.logo_recognition_template_filename": True,
        "landscape_analysis_result.recognized_idps.logo_recognition_template_scale": True,
        "landscape_analysis_result.recognized_idps.logo_recognition_screenshot_scale": True,
        "landscape_analysis_result.recognized_idps.logo_recognition_matching_score": True,
    },
    "project_login_page_candidates_metasearch": {
        "landscape_analysis_result.login_page_candidates.login_page_candidate": True,
        "landscape_analysis_result.login_page_candidates.login_page_strategy": True,
        "landscape_analysis_result.login_page_candidates.login_page_info.result_hit": True,
        "landscape_analysis_result.login_page_candidates.login_page_info.result_engines": True,
    },

    #### unwinds ####
    "unwind_idps": {
        "path": "$landscape_analysis_result.recognized_idps",
        "includeArrayIndex": "recognized_idps_index",
        "preserveNullAndEmptyArrays": False
    },
    "unwind_auto_consent_log": {
        "path": "$login_trace_analysis_result.auto_consent_log",
        "includeArrayIndex": "auto_consent_log_index",
        "preserveNullAndEmptyArrays": False
    },

    #### groups ####
    "group_by_domain": {
        "_id": "$domain",
        "resolved_domain": {"$first": "$landscape_analysis_result.resolved.domain"},
        "resolved_url": {"$first": "$landscape_analysis_result.resolved.url"}
    },
    "group_by_trace_lreq_method": {
        "_id": "$login_trace_analysis_result.idp_login_request_method",
        "count": {"$sum": 1}
    },
    "group_by_trace_lres_method": {
        "_id": "$login_trace_analysis_result.idp_login_response_method",
        "count": {"$sum": 1}
    },
    "group_by_trace_frame": {
        "_id": "$login_trace_analysis_result.idp_frame",
        "count": {"$sum": 1}
    },
    "group_by_trace_integration": {
        "_id": "$login_trace_analysis_result.idp_integration",
        "count": {"$sum": 1}
    },
    "group_by_auto_consent_log": {
        "_id": "$login_trace_analysis_result.auto_consent_log",
        "count": {"$sum": 1}
    },
}


def match_scan(db, scan_id=None, tag_name=None):
    if not scan_id and not tag_name:
        latest = []
        for c in db["scan_tags"].find({"tag_name": "latest"}):
            for sid in c["scan_ids"]:
                latest.append(sid)
        return {"scan_config.scan_id": {"$in": latest}}
    elif scan_id and not tag_name:
        return {"scan_config.scan_id": scan_id}
    elif not scan_id and tag_name:
        scan_ids = set()
        for c in db["scan_tags"].find({"tag_name": tag_name}):
            for sid in c["scan_ids"]:
                scan_ids.add(sid)
        return {"scan_config.scan_id": {"$in": list(scan_ids)}}
    else:
        scan_ids = set([scan_id])
        for c in db["scan_tags"].find({"tag_name": tag_name}):
            for sid in c["scan_ids"]:
                scan_ids.add(sid)
        return {"scan_config.scan_id": {"$in": list(scan_ids)}}


def match_latest(db):
    latest = []
    for c in db["scan_tags"].find({"tag_name": "latest"}):
        for sid in c["scan_ids"]:
            latest.append(sid)
    return {"scan_config.scan_id": {"$in": latest}}


def match_archived(db):
    latest = []
    for c in db["scan_tags"].find({"tag_name": "latest"}):
        for sid in c["scan_ids"]:
            latest.append(sid)
    return {"scan_config.scan_id": {"$nin": latest}}
