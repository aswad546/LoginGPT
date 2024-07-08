import logging
from playwright.sync_api import sync_playwright, TimeoutError, Error
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.tmp import TmpHelper
from modules.helper.auto_consent import AutoConsentHelper
from modules.helper.sso_interceptor import SSOInterceptorHelper


logger = logging.getLogger(__name__)


class LoginTraceAnalyzer:


    def __init__(self, domain: str, config: dict):
        self.domain = domain
        self.config = config

        self.browser_config = config["browser_config"]
        self.idp_name = config["idp_name"]
        self.idp_integration = config["idp_integration"]
        self.login_page_url = config["login_page_url"]
        self.element_coordinates_x = config["element_coordinates_x"]
        self.element_coordinates_y = config["element_coordinates_y"]
        self.element_width = config["element_width"]
        self.element_height = config["element_height"]
        self.idp_username = config["idp_username"]
        self.idp_password = config["idp_password"]
        self.idp_cookie_store = config["idp_cookie_store"]

        self.result = {}


    def start(self) -> dict:
        logger.info(f"Starting login trace analysis for idp {self.idp_name} on: {self.login_page_url}")

        with TmpHelper.tmp_dir() as pdir, TmpHelper.tmp_file() as har, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir, har_file=har)
            auto_consent = AutoConsentHelper(
                context, page,
                self.idp_name, self.idp_integration,
                self.idp_username, self.idp_password, self.idp_cookie_store
            )

            # load idp cookies to skip reauthentication on the idp
            auto_consent.load_idp_cookies()

            try:
                # start sso interceptor
                sso_interceptor = SSOInterceptorHelper(context, self.idp_name, self.idp_integration)
                sso_interceptor.start_intercept()

                # navigate to login page
                logger.info(f"Navigate to login page: {self.login_page_url}")
                PlaywrightHelper.navigate(page, self.login_page_url, self.browser_config)
                PlaywrightHelper.sleep(page, 5)

                # click on coordinate and wait for popup
                if self.idp_integration != "GOOGLE_ONE_TAP":
                    try:
                        x = self.element_coordinates_x + self.element_width/2
                        y = self.element_coordinates_y + self.element_height/2
                        with page.expect_popup(timeout=2_000) as page_info:
                            logger.info(f"Clicking on coordinate ({x}, {y}) and waiting for popup")
                            page.mouse.click(x, y)
                        logger.info("Popup opened after clicking coordinate, waiting for popup to load")
                        PlaywrightHelper.sleep(page_info.value, 30) # run auto consent
                        self.result["idp_frame"] = "POPUP"
                    except TimeoutError:
                        logger.info("No popup opened after clicking coordinate, waiting for page to load")
                        PlaywrightHelper.sleep(page, 30) # run auto consent
                        self.result["idp_frame"] = "TOPMOST"
                    except Error:
                        logger.info("Popup immediately closed after opening, could not wait for popup to load")
                        PlaywrightHelper.sleep(page, 30) # run auto consent
                        self.result["idp_frame"] = "POPUP"

                # wait for auto consent to execute the google one tap
                else:
                    PlaywrightHelper.sleep(page, 30)
                    if not sso_interceptor.idp_login_request:
                        PlaywrightHelper.reload(page, self.browser_config)
                        PlaywrightHelper.sleep(page, 30)
                    self.result["idp_frame"] = "IFRAME"

                # stop sso interceptor
                sso_interceptor.stop_intercept()

                # store idp cookies to skip reauthentication on the idp
                auto_consent.store_idp_cookies()

                # store result
                self.result.update({
                    **sso_interceptor.get_idp_interceptions(),
                    "auto_consent_log": auto_consent.log,
                    "login_trace_screenshot": PlaywrightHelper.take_screenshot(page),
                    "login_trace_storage_state": PlaywrightHelper.take_storage_state(context)
                })

                # close context
                PlaywrightHelper.close_context(context)

                # store har
                self.result["login_trace_har"] = PlaywrightHelper.take_har(har)

            except TimeoutError as e:
                logger.warning(f"Timeout during login trace analysis for idp {self.idp_name} on: {self.login_page_url}")
                logger.debug(e)
                self.result = {"error": "Timeout"}

            except Error as e:
                logger.warning(f"Error during login trace analysis for idp {self.idp_name} on: {self.login_page_url}")
                logger.debug(e)
                self.result = {"error": f"{e}"}

        return self.result
