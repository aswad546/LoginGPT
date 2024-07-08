import json
import re
from urllib.parse import urlparse, parse_qs
from apiflask import APIBlueprint
from apiflask.fields import String
from flask import current_app
from modules.queries import q, match_scan


bp_wra = APIBlueprint("wra", __name__, url_prefix="/wra")


@bp_wra.get("/")
@bp_wra.input({"scan_id": String(required=True)}, location="query")
def wildcard_receiver_attack(query_data):
    db = current_app.config["db"]
    scan_id = query_data["scan_id"]

    PATTERNS = {
        "GOOGLE_CODE": ["4/", "4%2F"],
        "GOOGLE_ACCESS_TOKEN": ["ya29"],
        "GOOGLE_ID_TOKEN": ["eyJpc3MiOiJhY2NvdW50cy5nb29nbGUuY29tIi", "eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20i"],
        "GOOGLE_REFRESH_TOKEN": ["1//", "1%2F%2F"],
        "CLIENT_SECRET": ["client_secret", "app_secret"],
        "EMAIL": ["ssomonitorme.*@gmail\.com"],
        "NAME": ["sso monitor me"],
        "PROFILE_PICTURE": ["https://lh3\.googleusercontent\.com/a/"],
        "JWT": ["ey.*\.ey.*\..*"],
        "BASE64": ["eyJ"],
        "PASSWORD": ["password\":", "password="],
        "FIREBASE_JWT": ["firebase_jwt"],
        "UNCONFIRMED_TOKEN": [
            "[?&]access[_]?token=", "access[_]?token[\"\']:",
            "[?&]token=", "token[\"\']:", "[?&]refresh[_]?token=", "refresh[_]?token[\"\']:",
            "[?&]refresh=", "refresh[\"\']:", "[?&]code=", "code[\"\']:"
        ],
        "UNCONFIRMED_STATE": [
            "[?&]state=", "state[\"\']:", "[?&]state[_]?token=", "state[_]?token[\"\']:",
            "[?&]state[_]?key=", "state[_]?key[\"\']:"
        ],
        "UNCONFIRMED_ID": ["[?&]id=", "id[\"\']:"],
        "IDB_ULOGIN": ['"mine": "uLogin"'],
        "IDB_SHOPIFY_OPEN_SIGNIN": ["postLoginMultipass", "\$1\$SiGnIn-\$"],
        "IDB_SHOPIFY_ONE_CLICK_SOCIAL_LOGIN": ["one_click_social_login_"],
        "IDB_ZEPHR": ["fromZeph"],
        "IDB_HARAVAN": ["haravanAccountLogin"]
    }

    result = {"domains": [], "leaks": [], "patterns": {}, "count": {}}
    pipeline = [
        {"$project": {**q["project_base"], **q["project_wra_exploitation_stage"]}},
        {"$match": {**match_scan(db, scan_id, None), **q["match_pm_leaks"]}}
    ]
    for c in db["wildcard_receiver_analysis_tres"].aggregate(pipeline):
        domain = c["domain"]
        leaks = c["wildcard_receiver_analysis_result"]["exploitation_stage"]["postmessage_leaks"]
        lreq = c["wildcard_receiver_analysis_result"]["exploitation_stage"]["idp_login_request"]
        state = parse_qs(urlparse(lreq).query).get("state", [""])[0]
        result["domains"].append(domain)
        for l in leaks:
            data = l["data"]
            datastring = json.dumps(data)
            result["leaks"].append((domain, datastring))
            # check state
            if state and state in datastring:
                if "CONFIRMED_STATE" not in result["patterns"]:
                    result["patterns"]["CONFIRMED_STATE"] = []
                result["patterns"]["CONFIRMED_STATE"].append((domain, datastring))
            # check patterns
            for pattern in PATTERNS:
                for p in PATTERNS[pattern]:
                    regex = re.compile(p, re.IGNORECASE)
                    if regex.search(datastring):
                        if pattern not in result["patterns"]:
                            result["patterns"][pattern] = []
                        result["patterns"][pattern].append((domain, datastring))
                        break
    for pattern in result["patterns"]:
        result["count"][pattern] = len(result["patterns"][pattern])

    return {"success": True, "error": None, "data": result}
