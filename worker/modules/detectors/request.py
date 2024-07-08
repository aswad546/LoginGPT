import logging
from playwright.sync_api import BrowserContext, Request
from config.idp_rules import IdpRules
from modules.helper.url import URLHelper


logger = logging.getLogger(__name__)


class RequestDetector:


    def __init__(self, config: dict, result: dict, context: BrowserContext):
        self.config = config
        self.result = result
        self.context = context


    def register_interceptor(self, lpc_url: str, lpc_reloaded: bool):
        logger.info(f"Registering request interceptor {'(reloaded)' if lpc_reloaded else ''} for: {lpc_url}")
        self.lpc_url = lpc_url
        self.lpc_reloaded = lpc_reloaded
        self.context.on("request", self.interceptor)


    def unregister_interceptor(self):
        logger.info("Unregistering request interceptor")
        self.context.remove_listener("request", self.interceptor)


    def interceptor(self, request: Request):

        # passive login requests
        for idp in IdpRules:
            plreq_rule = IdpRules[idp]["passive_login_request_rule"]
            if plreq_rule and URLHelper.match_url(
                request.url,
                plreq_rule["domain"], plreq_rule["path"], plreq_rule["params"]
            ):
                logger.info(f"Matched passive login request for idp {idp}: {request.url}")
                if not any(
                    ridp["idp_name"] == idp
                    and ridp["login_page_url"] == self.lpc_url
                    and ridp["recognition_strategy"] == "REQUEST"
                    for ridp in self.result["recognized_idps_passive"]
                ):
                    logger.info(f"Adding passive login request to recognized idps")
                    self.result["recognized_idps_passive"].append({
                        "idp_name": idp,
                        "login_page_url": self.lpc_url,
                        "login_page_reloaded": self.lpc_reloaded,
                        "recognition_strategy": "REQUEST",
                        "idp_frame": "IFRAME", # google one tap sdk is always iframe
                        "idp_login_request": request.url
                    })
                else:
                    logger.info(f"Skipping already recognized passive login request")
