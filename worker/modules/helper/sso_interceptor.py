import logging
from playwright.sync_api import BrowserContext, Request
from modules.helper.url import URLHelper
from config.idp_rules import IdpRules


logger = logging.getLogger(__name__)


class SSOInterceptorHelper:


    def __init__(self, context: BrowserContext, idp_name: str, idp_integration: str|None = None):
        self.context = context
        self.idp_name = idp_name
        self.idp_integration = idp_integration

        self.idp_login_request = None
        self.idp_login_request_method = None
        self.idp_login_response = None
        self.idp_login_response_method = None
        self.idp_login_response_post_data = None
        self.idp_login_response_postmessage = None
        self.idp_login_response_channelmessage = None

        self.login_attempt_leaks = []
        self.token_exchange_leaks = []


    def start_intercept(self):
        logger.info("Starting interception of sso messages")
        self.context.on("request", self.interceptor)


    def stop_intercept(self):
        logger.info("Stopping interception of sso messages")
        self.context.remove_listener("request", self.interceptor)


    def get_idp_interceptions(self):
        return {
            "idp_login_request": self.idp_login_request,
            "idp_login_request_method": self.idp_login_request_method,
            "idp_login_response": self.idp_login_response,
            "idp_login_response_method": self.idp_login_response_method,
            "idp_login_response_post_data": self.idp_login_response_post_data,
            "idp_login_response_postmessage": self.idp_login_response_postmessage,
            "idp_login_response_channelmessage": self.idp_login_response_channelmessage,
            "idp_integration": self.get_idp_integration()
        }


    def get_idp_leaks(self):
        return {
            "login_attempt_leaks": self.login_attempt_leaks,
            "token_exchange_leaks": self.token_exchange_leaks
        }


    def get_idp_integration(self):
        logger.info(f"Determine integration for login request url: {self.idp_login_request}")
        if self.idp_login_request is None: return None
        for integration, rules in IdpRules[self.idp_name]["sdks"].items():
            logger.info(f"Matching login request url against rule: {rules['login_request_rule']}")
            if URLHelper.match_url(
                self.idp_login_request,
                rules["login_request_rule"]["domain"],
                rules["login_request_rule"]["path"],
                rules["login_request_rule"]["params"]
            ):
                logger.info(f"Matched login request url for integration: {integration}")
                return integration # use first integration rule that matches


    def interceptor(self, request: Request):
        logger.debug(f"Intercepted request url: {request.url}")

        response = request.response()
        if response: logger.debug(f"Intercepted response url: {response.url}")

        # GET login request
        if (
            self.idp_login_request is None
            and ((
                self.idp_integration != "GOOGLE_ONE_TAP"
                and request.is_navigation_request()
                and URLHelper.match_url(
                    request.url,
                    IdpRules[self.idp_name]["login_request_rule"]["domain"],
                    IdpRules[self.idp_name]["login_request_rule"]["path"],
                    IdpRules[self.idp_name]["login_request_rule"]["params"]
                )
            ) or (
                self.idp_integration == "GOOGLE_ONE_TAP"
                and URLHelper.match_url(
                    request.url,
                    IdpRules[self.idp_name]["passive_login_request_rule"]["domain"],
                    IdpRules[self.idp_name]["passive_login_request_rule"]["path"],
                    IdpRules[self.idp_name]["passive_login_request_rule"]["params"]
                )
            ))
        ):
            logger.info(f"Matched login request url: {request.url}")
            self.idp_login_request = request.url
            self.idp_login_request_method = "GET"

        # GET login response -> response_mode=query|fragment
        if (
            self.idp_login_response is None
            and response
            and response.header_value("location")
            and URLHelper.match_url(
                response.header_value("location"),
                IdpRules[self.idp_name]["login_response_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_rule"]["path"],
                IdpRules[self.idp_name]["login_response_rule"]["params"]
            )
            and URLHelper.match_url(
                request.url,
                IdpRules[self.idp_name]["login_response_originator_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["path"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["params"]
            )
        ):
            logger.info(f"Matched login response url: {response.header_value('location')}")
            self.idp_login_response = response.header_value("location")
            self.idp_login_response_method = "GET"

        # POST login response -> response_mode=form_post
        if (
            self.idp_login_response is None
            and request.is_navigation_request()
            and request.method == "POST"
            and request.post_data_json
            and URLHelper.match_post_data(
                request.url,
                request.post_data_json,
                IdpRules[self.idp_name]["login_response_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_rule"]["path"],
                IdpRules[self.idp_name]["login_response_rule"]["params"]
            )
            and request.header_value("origin")
            and URLHelper.match_url(
                request.header_value("origin"),
                IdpRules[self.idp_name]["login_response_originator_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["path"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["params"]
            )
        ):
            logger.info(f"Matched login response url: {request.url}")
            self.idp_login_response = request.url
            self.idp_login_response_method = "POST"
            self.idp_login_response_post_data = request.post_data_json

        # POSTMESSAGE login response -> GOOGLE_SIGN_IN_DEPRECATED
        pm = URLHelper.parse_inbc(request, "POSTMESSAGE")
        if (
            self.idp_login_response is None
            and pm
            and URLHelper.match_inbc_data(
                pm["data"],
                IdpRules[self.idp_name]["login_response_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_rule"]["path"],
                IdpRules[self.idp_name]["login_response_rule"]["params"]
            )
            and pm["initiator_origin"]
            and URLHelper.match_url(
                pm["initiator_origin"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["path"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["params"]
            )
        ):
            logger.info(f"Matched login response url: {request.url}")
            self.idp_login_response = request.url
            self.idp_login_response_method = "POSTMESSAGE"
            self.idp_login_response_postmessage = pm

        # CHANNELMESSAGE login response -> SIGN_IN_WITH_GOOGLE
        cm = URLHelper.parse_inbc(request, "CHANNELMESSAGE")
        if (
            self.idp_login_response is None
            and cm
            and URLHelper.match_inbc_data(
                cm["data"],
                IdpRules[self.idp_name]["login_response_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_rule"]["path"],
                IdpRules[self.idp_name]["login_response_rule"]["params"]
            )
            and cm["initiator_origin"]
            and URLHelper.match_url(
                cm["initiator_origin"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["domain"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["path"],
                IdpRules[self.idp_name]["login_response_originator_rule"]["params"]
            )
        ):
            logger.info(f"Matched login response url: {request.url}")
            self.idp_login_response = request.url
            self.idp_login_response_method = "CHANNELMESSAGE"
            self.idp_login_response_channelmessage = cm

        # login attempt leak
        if (
            "login_attempt_leak_rule" in IdpRules[self.idp_name]
            and URLHelper.match_url(
                request.url,
                IdpRules[self.idp_name]["login_attempt_leak_rule"]["domain"],
                IdpRules[self.idp_name]["login_attempt_leak_rule"]["path"],
                IdpRules[self.idp_name]["login_attempt_leak_rule"]["params"]
            )
        ):
            logger.info(f"Matched login attempt leak url: {request.url}")
            self.login_attempt_leaks.append(request.url)

        # token exchange leak
        if (
            "token_exchange_leak_rule" in IdpRules[self.idp_name]
            and URLHelper.match_url(
                request.url,
                IdpRules[self.idp_name]["token_exchange_leak_rule"]["domain"],
                IdpRules[self.idp_name]["token_exchange_leak_rule"]["path"],
                IdpRules[self.idp_name]["token_exchange_leak_rule"]["params"]
            )
        ):
            logger.info(f"Matched token exchange leak url: {request.url}")
            self.token_exchange_leaks.append(request.url)
