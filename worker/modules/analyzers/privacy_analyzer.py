import logging
from enum import Enum
from copy import deepcopy
from playwright.sync_api import sync_playwright, TimeoutError, Error
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.tmp import TmpHelper
from modules.helper.auto_consent import AutoConsentHelper
from modules.helper.sso_interceptor import SSOInterceptorHelper


logger = logging.getLogger(__name__)


class PrivacyAnalyzer:


    COOKIE_POLICY = Enum("COOKIE_POLICY", ["IGNORE", "ACCEPT_ALL", "DENY_ALL"])


    def __init__(self, domain: str, config: dict):
        self.domain = domain
        self.config = config

        self.browser_config = config["browser_config"]
        self.idp_name = config["idp_name"]
        self.idp_integration = config["idp_integration"]
        self.login_page_url = config["login_page_url"]
        self.idp_username = config["idp_username"]
        self.idp_password = config["idp_password"]
        self.idp_cookie_store = config["idp_cookie_store"]

        self.result = {}


    def start(self) -> dict:
        logger.info(f"Starting privacy analysis for idp {self.idp_name} on: {self.login_page_url}")

        # no cookie banner actions, no auth and consent on idp
        self.result["ignore_cookie_no_auth"] = self.no_auth(self.COOKIE_POLICY.IGNORE)

        # accept cookie banner, no auth and consent on idp
        self.result["accept_cookie_no_auth"] = self.no_auth(self.COOKIE_POLICY.ACCEPT_ALL)

        return self.result


    def no_auth(self, cookie_policy: COOKIE_POLICY) -> dict:
        logger.info(f"Starting privacy analysis (no auth, {cookie_policy}) for idp {self.idp_name} on: {self.login_page_url}")

        # prepare browser config for cookie policy
        browser_config = deepcopy(self.browser_config)
        if cookie_policy == self.COOKIE_POLICY.IGNORE:
            browser_config["extensions"] = []
            browser_config["scripts"] = []
        elif cookie_policy == self.COOKIE_POLICY.ACCEPT_ALL:
            pass
        elif cookie_policy == self.COOKIE_POLICY.DENY_ALL:
            pass

        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, browser_config, pdir)

            try:
                # start sso interceptor
                sso_interceptor = SSOInterceptorHelper(context, self.idp_name, self.idp_integration)
                sso_interceptor.start_intercept()

                # navigate to login page
                logger.info(f"Navigate to login page: {self.login_page_url}")
                PlaywrightHelper.navigate(page, self.login_page_url, browser_config)
                PlaywrightHelper.sleep(page, 5)

                # reload login page if no leaks observed
                login_page_reloaded = False
                if (
                    not sso_interceptor.login_attempt_leaks
                    and not sso_interceptor.token_exchange_leaks
                ):
                    PlaywrightHelper.reload(page, browser_config)
                    PlaywrightHelper.sleep(page, 5)
                    login_page_reloaded = True

                # stop sso interceptor
                sso_interceptor.stop_intercept()

                # close context
                PlaywrightHelper.close_context(context)

                return {
                    "login_page_reloaded": login_page_reloaded,
                    "idp_leaks": sso_interceptor.get_idp_leaks(),
                    "idp_interceptions": sso_interceptor.get_idp_interceptions()
                }

            except TimeoutError as e:
                logger.warning(f"Timeout during privacy analysis (no auth, {cookie_policy}) for idp {self.idp_name} on: {self.login_page_url}")
                logger.warning(e)
                return {"error": "Timeout"}

            except Error as e:
                logger.warning(f"Error during privacy analysis (no auth, {cookie_policy}) for idp {self.idp_name} on: {self.login_page_url}")
                logger.warning(e)
                return {"error": f"{e}"}
