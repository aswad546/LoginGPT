import os
import json
import logging
from playwright.sync_api import TimeoutError, Error, BrowserContext, Page
from modules.browser.browser import PlaywrightHelper


logger = logging.getLogger(__name__)


class AutoConsentHelper:


    TMP_PATH = os.environ.get("TMP_PATH", "/tmpfs")


    IDP_COOKIE_URLS = {
        "GOOGLE": [
            "https://accounts.google.com"
        ]
    }


    def __init__(
        self,
        context: BrowserContext, page: Page,
        idp_name: str, idp_integration: str,
        idp_username: str, idp_password: str, idp_cookie_store: str
    ):
        logger.info(f"Initializing auto consent for idp: {idp_name}")

        self.context = context
        self.page = page
        self.idp_name = idp_name
        self.idp_integration = idp_integration
        self.idp_username = idp_username
        self.idp_password = idp_password
        self.idp_cookie_store = idp_cookie_store

        # stores log of auto consent process
        self.log = []

        # path to local idp cookie store to skip future reauthentication on the idp
        self.local_idp_cookie_store = f"{self.TMP_PATH}/idp_cookie_store_{self.idp_name}_{self.idp_username}.json"

        # callback is executed on page load and executes the auto consent process
        if idp_name == "GOOGLE": self.auto_consent_cb = self.auto_consent_google
        else: raise Exception(f"Login tracer does not support the idp: {idp_name}")

        # register consent callback to be executed on page load
        context.on("page", lambda page: page.on("load", self.auto_consent_cb))
        page.on("load", self.auto_consent_cb)

        # suppress auto login feature of google one tap sdk
        def handle_route(route):
            url = route.request.url
            new_url = url.replace("auto_select=true", "auto_select=false")
            route.continue_(url=new_url)
        context.route("https://accounts.google.com/gsi/iframe/select**", handle_route)


    def load_idp_cookies(self):
        # use local cookie store if it is available
        try:
            logger.info(f"Loading cookies for idp {self.idp_name} from: {self.local_idp_cookie_store}")
            with open(self.local_idp_cookie_store, "r") as f:
                try: cookies = json.load(f)
                except json.JSONDecodeError: cookies = []
                self.context.add_cookies(cookies)
            logger.info(f"Loaded cookies for idp {self.idp_name} from: {self.local_idp_cookie_store}")
        # use cookie store from config if local cookie store is not available
        except FileNotFoundError:
            logger.info(f"Loading cookies for idp {self.idp_name} from cookie store in config")
            try: cookies = json.loads(self.idp_cookie_store)
            except json.JSONDecodeError: cookies = []
            self.context.add_cookies(cookies)
            logger.info(f"Loaded cookies for idp {self.idp_name} from cookie store in config")


    def store_idp_cookies(self):
        logger.info(f"Storing cookies for idp {self.idp_name} in: {self.local_idp_cookie_store}")
        with open(self.local_idp_cookie_store, "w") as f:
            json.dump(self.context.cookies(urls=self.IDP_COOKIE_URLS[self.idp_name]), f, indent=4)


    def auto_consent_google(self, page: Page):
        logger.info(f"Running auto consent google on: {page.url}")
        PlaywrightHelper.sleep(page, 5)

        # login
        if (
            PlaywrightHelper.hostname(page) == "accounts.google.com"
            and (
                PlaywrightHelper.pathname(page).endswith("/identifier")
                or PlaywrightHelper.pathname(page).endswith("/challenge/ipp")
            )
        ):
            self.log.append("match_login")
            # username
            try:
                logger.info(f"Fill username: {self.idp_username}")
                page.get_by_label("email").first.fill(self.idp_username, timeout=5_000)
                logger.info(f"Press enter")
                page.keyboard.press("Enter")
                self.log.append("fill_username")
            except TimeoutError:
                logger.info(f"Cannot fill username due to timeout")
                self.log.append("timeout_username")
            except Error:
                logger.info(f"Cannot fill username due to closed page")
                self.log.append("error_username")
            # password
            try:
                logger.info(f"Fill password: {self.idp_password}")
                page.get_by_label("password").first.fill(self.idp_password, timeout=5_000)
                logger.info(f"Press enter")
                page.keyboard.press("Enter")
                self.log.append("fill_password")
            except TimeoutError:
                logger.info(f"Cannot fill password due to timeout")
                self.log.append("timeout_password")
            except Error:
                logger.info(f"Cannot fill password due to closed page")
                self.log.append("error_password")

        # account chooser
        if (
            PlaywrightHelper.hostname(page) == "accounts.google.com"
            and (
                PlaywrightHelper.pathname(page).endswith("/signinchooser")
                or PlaywrightHelper.pathname(page).endswith("/oauthchooseaccount")
            )
        ):
            self.log.append("match_accountchooser")
            # username
            try:
                logger.info(f"Select username")
                first_account = page.locator("[data-identifier]").first
                first_account.wait_for(timeout=5_000)
                first_account.click()
                self.log.append("fill_username")
            except TimeoutError:
                logger.info("Cannot select username due to timeout")
                self.log.append("timeout_username")
            except Error:
                logger.info("Cannot select username due to closed page")
                self.log.append("error_username")
            # password
            try:
                logger.info(f"Fill password: {self.idp_password}")
                page.locator("input[type='password']").first.fill(self.idp_password, timeout=5_000)
                logger.info(f"Press enter")
                page.keyboard.press("Enter")
                self.log.append("fill_password")
            except TimeoutError:
                logger.info(f"Cannot fill password due to timeout")
                self.log.append("timeout_password")
            except Error:
                logger.info(f"Cannot fill password due to closed page")
                self.log.append("error_password")

        # consent sdk (sign in with google)
        if (
            PlaywrightHelper.hostname(page) == "accounts.google.com"
            and (
                PlaywrightHelper.pathname(page) == "/gsi/select"
                or PlaywrightHelper.pathname(page) == "/gsi/confirm"
            )
        ):
            self.log.append("match_consent_sdk_siwg")
            # account btn
            try:
                logger.info("Waiting for account button")
                account_btn = page.locator("[role=link]").first
                account_btn.wait_for(timeout=5_000)
                logger.info("Click account button")
                account_btn.click()
                self.log.append("click_account_btn")
            except TimeoutError:
                logger.info("Cannot click account button due to timeout")
                self.log.append("timeout_account_btn")
            except Error:
                logger.info("Cannot click account button due to closed page")
                self.log.append("error_account_btn")
            # confirm btn
            try:
                logger.info("Waiting for confirm button")
                confirm_btn = page.locator("#confirm_yes").first
                confirm_btn.wait_for(timeout=5_000)
                logger.info("Click confirm button")
                confirm_btn.click()
                self.log.append("click_confirm_btn")
            except TimeoutError:
                logger.info("Cannot click confirm button due to timeout")
                self.log.append("timeout_confirm_btn")
            except Error:
                logger.info("Cannot click confirm button due to closed page")
                self.log.append("error_confirm_btn")

        # consent sdk (google one tap)
        for frame in page.frames:
            if (
                self.idp_integration == "GOOGLE_ONE_TAP"
                and PlaywrightHelper.hostname(frame) == "accounts.google.com"
                and PlaywrightHelper.pathname(frame) == "/gsi/iframe/select"
            ):
                self.log.append("match_consent_sdk_got")
                # continue btn
                try:
                    logger.info("Waiting for continue button")
                    continue_btn = frame.locator("button").first
                    continue_btn.wait_for(timeout=5_000)
                    logger.info("Click continue button")
                    continue_btn.click()
                    self.log.append("click_continue_btn")
                except TimeoutError:
                    logger.info("Cannot click continue button due to timeout")
                    self.log.append("timeout_continue_btn")
                except Error:
                    logger.info("Cannot click continue button due to closed page")
                    self.log.append("error_continue_btn")

        # consent sensitive (sensitive scopes requested)
        if (
            PlaywrightHelper.hostname(page) == "accounts.google.com"
            and (
                PlaywrightHelper.pathname(page).endswith("/consent")
                or PlaywrightHelper.pathname(page).endswith("/consentsummary")
            )
        ):
            self.log.append("match_consent_sensitive")
            # allow button
            try:
                logger.info("Waiting for allow button")
                allow_btn = page.locator("#submit_approve_access > div > button").first
                allow_btn.wait_for(timeout=5_000)
                logger.info("Click allow button")
                allow_btn.click()
                self.log.append("click_allow_btn")
            except TimeoutError:
                logger.info("Cannot click allow button due to timeout")
                self.log.append("timeout_allow_btn")
            except Error:
                logger.info("Cannot click allow button due to closed page")
                self.log.append("error_allow_btn")
