from math import ceil
from apiflask import APIBlueprint
from apiflask.fields import String
from flask import current_app
from config.cache import cache


bp_gt = APIBlueprint("gt", __name__, url_prefix="/gt")


@bp_gt.get("/")
@bp_gt.input({"gt_id": String(required=True)}, location="query")
@cache.cached(query_string=True)
def ground_truth_statistics(query_data):
    db = current_app.config["db"]
    gt_id = query_data["gt_id"]

    domains_all = db["ground_truth"].find({"gt_id": gt_id}).distinct("domain")
    domains_not_reachable = db["ground_truth"].find({"gt_id": gt_id, "reachable": False}).distinct("domain")
    domains_with_sso = db["ground_truth"].find({"gt_id": gt_id, "sso": True}).distinct("domain")
    domains_without_sso = db["ground_truth"].find({"gt_id": gt_id, "sso": False}).distinct("domain")
    domains_with_login = db["ground_truth"].find({"gt_id": gt_id, "login": True}).distinct("domain")
    domains_without_login = db["ground_truth"].find({"gt_id": gt_id, "login": False}).distinct("domain")
    domains_with_login_without_sso = db["ground_truth"].find({"gt_id": gt_id, "login": True, "sso": False}).distinct("domain")
    domains_with_sso_without_error = db["ground_truth"].find({"gt_id": gt_id, "sso": True, "sso_error": {"$in": [False, None]}}).distinct("domain")
    domains_with_sso_with_error = db["ground_truth"].find({"gt_id": gt_id, "sso": True, "sso_error": True}).distinct("domain")
    domains_with_sso_with_interaction = db["ground_truth"].find({"gt_id": gt_id, "sso": True, "interaction_required": True}).distinct("domain")
    domains_with_sso_without_interaction = db["ground_truth"].find({"gt_id": gt_id, "sso": True, "interaction_required": False}).distinct("domain")

    buttons_all = [d["domain"] for d in db["ground_truth"].find({"gt_id": gt_id, "sso": True})]
    buttons_with_error = [d["domain"] for d in db["ground_truth"].find({"gt_id": gt_id, "sso": True, "sso_error": True})]
    buttons_without_error = [d["domain"] for d in db["ground_truth"].find({"gt_id": gt_id, "sso": True, "sso_error": {"$in": [False, None]}})]
    buttons_with_interaction = [d["domain"] for d in db["ground_truth"].find({"gt_id": gt_id, "sso": True, "sso_error": {"$in": [False, None]}, "interaction_required": True})]
    buttons_without_interaction = [d["domain"] for d in db["ground_truth"].find({"gt_id": gt_id, "sso": True, "sso_error": {"$in": [False, None]}, "interaction_required": False})]

    idps = {}
    idps_errorless_interactionless = {}
    for c in db["ground_truth"].find({"gt_id": gt_id, "idp_name": {"$ne": None}}):
        if c["idp_name"] not in idps:
            idps[c["idp_name"]] = []
        idps[c["idp_name"]].append(c["domain"])
        if c["sso_error"] != True and c["interaction_required"] == False:
            if c["idp_name"] not in idps_errorless_interactionless:
                idps_errorless_interactionless[c["idp_name"]] = []
            idps_errorless_interactionless[c["idp_name"]].append(c["domain"])

    frames = {}
    for c in db["ground_truth"].find({"gt_id": gt_id, "idp_frame": {"$ne": None}}):
        if c["idp_frame"] not in frames:
            frames[c["idp_frame"]] = []
        frames[c["idp_frame"]].append(c["domain"])

    sdks = {}
    flows = {}
    integrations = {"CUSTOM": [], "SDK": []}
    for c in db["ground_truth"].find({"gt_id": gt_id, "idp_integration": {"$ne": None}}):
        if c["idp_integration"] == "CUSTOM":
            integrations["CUSTOM"].append(c["domain"])
            if c["idp_frame"]:
                if f"CUSTOM_{c['idp_frame']}" not in flows:
                    flows[f"CUSTOM_{c['idp_frame']}"] = []
                flows[f"CUSTOM_{c['idp_frame']}"].append(c["domain"])
        elif c["idp_integration"] == "N/A":
            pass
        else:
            integrations["SDK"].append(c["domain"])
            if c["idp_integration"] not in sdks:
                sdks[c["idp_integration"]] = []
            sdks[c["idp_integration"]].append(c["domain"])
            if c["idp_frame"]:
                if f"SDK_{c['idp_frame']}" not in flows:
                    flows[f"SDK_{c['idp_frame']}"] = []
                flows[f"SDK_{c['idp_frame']}"].append(c["domain"])

    sso_by_rank = {}
    max_rank = db["ground_truth"].find({"gt_id": gt_id}).sort("rank", -1).limit(1)[0]["rank"]
    range = int(max_rank / 50)
    for c in db["ground_truth"].find({"gt_id": gt_id, "idp_name": {"$ne": None}}):
        marker = ceil(c["rank"] / float(range)) * range
        key = f"{marker-range}"
        if key not in sso_by_rank:
            sso_by_rank[key] = []
        sso_by_rank[key].append(c["domain"])

    return {
        "success": True,
        "error": None,
        "data": {
            "domains_all": len(domains_all),
            "_domains_all": domains_all,
            "domains_not_reachable": len(domains_not_reachable),
            "_domains_not_reachable": domains_not_reachable,
            "domains_with_sso": len(domains_with_sso),
            "_domains_with_sso": domains_with_sso,
            "domains_without_sso": len(domains_without_sso),
            "_domains_without_sso": domains_without_sso,
            "domains_with_login": len(domains_with_login),
            "_domains_with_login": domains_with_login,
            "domains_without_login": len(domains_without_login),
            "_domains_without_login": domains_without_login,
            "domains_with_login_without_sso": len(domains_with_login_without_sso),
            "_domains_with_login_without_sso": domains_with_login_without_sso,
            "domains_with_sso_without_error": len(domains_with_sso_without_error),
            "_domains_with_sso_without_error": domains_with_sso_without_error,
            "domains_with_sso_with_error": len(domains_with_sso_with_error),
            "_domains_with_sso_with_error": domains_with_sso_with_error,
            "domains_with_sso_with_interaction": len(domains_with_sso_with_interaction),
            "_domains_with_sso_with_interaction": domains_with_sso_with_interaction,
            "domains_with_sso_without_interaction": len(domains_with_sso_without_interaction),
            "_domains_with_sso_without_interaction": domains_with_sso_without_interaction,

            "domains_idps": {k: len(set(v)) for k, v in idps_errorless_interactionless.items()},
            "_domains_idps": {k: list(set(v)) for k, v in idps_errorless_interactionless.items()},
            "domains_idps_with_error_with_interaction": {k: len(set(v)) for k, v in idps.items()},
            "_domains_idps_with_error_with_interaction": {k: list(set(v)) for k, v in idps.items()},
            "domains_integrations": {k: len(set(v)) for k, v in integrations.items()},
            "_domains_integrations": {k: list(set(v)) for k, v in integrations.items()},
            "domains_sdks": {k: len(set(v)) for k, v in sdks.items()},
            "_domains_sdks": {k: list(set(v)) for k, v in sdks.items()},
            "domains_frames": {k: len(set(v)) for k, v in frames.items()},
            "_domains_frames": {k: list(set(v)) for k, v in frames.items()},
            "domains_flows": {k: len(set(v)) for k, v in flows.items()},
            "_domains_flows": {k: list(set(v)) for k, v in flows.items()},
            "domains_with_sso_by_rank": {k: len(set(v)) for k, v in sso_by_rank.items()},
            "_domains_with_sso_by_rank": {k: list(set(v)) for k, v in sso_by_rank.items()},

            "buttons_all": len(buttons_all),
            "_buttons_all": buttons_all,
            "buttons_with_error": len(buttons_with_error),
            "_buttons_with_error": buttons_with_error,
            "buttons_without_error": len(buttons_without_error),
            "_buttons_without_error": buttons_without_error,
            "buttons_with_interaction": len(buttons_with_interaction),
            "_buttons_with_interaction": buttons_with_interaction,
            "buttons_without_interaction": len(buttons_without_interaction),
            "_buttons_without_interaction": buttons_without_interaction,

            "buttons_idps": {k: len(v) for k, v in idps_errorless_interactionless.items()},
            "_buttons_idps": idps_errorless_interactionless,
            "buttons_idps_with_error_with_interaction": {k: len(v) for k, v in idps.items()},
            "_buttons_idps_with_error_with_interaction": idps,
            "buttons_integrations": {k: len(v) for k, v in integrations.items()},
            "_buttons_integrations": integrations,
            "buttons_sdks": {k: len(v) for k, v in sdks.items()},
            "_buttons_sdks": sdks,
            "buttons_frames": {k: len(v) for k, v in frames.items()},
            "_buttons_frames": frames,
            "buttons_flows": {k: len(v) for k, v in flows.items()},
            "_buttons_flows": flows,
            "buttons_by_rank": {k: len(v) for k, v in sso_by_rank.items()},
            "_buttons_by_rank": sso_by_rank
        }
    }
