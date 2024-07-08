import os
import logging
import base64
import zlib
import requests
from uuid import uuid4
from pathlib import Path
from typing import Tuple, List
from urllib.parse import urlparse
from playwright.sync_api import TimeoutError, Page, BrowserContext
from playwright.sync_api._generated import Playwright


logger = logging.getLogger(__name__)


class RequestsBrowser:


    @staticmethod
    def chrome_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "dnt": "1",
            "Pragma": "no-cache",
            "sec-ch-ua": '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "macOS",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "Upgrade-Insecure-Requests": "1"
        })
        return session


class PlaywrightHelper:


    @staticmethod
    def navigate(page: Page, url: str, browser_config: dict = {}):
        logger.info(f"Page loads url: {url}")
        page.goto(url)
        PlaywrightHelper.wait_for_page_load(page, browser_config)


    @staticmethod
    def sleep(page: Page, seconds: int):
        logger.info(f"Sleeping {seconds} seconds")
        page.wait_for_timeout(seconds*1000)


    @staticmethod
    def reload(page: Page, browser_config: dict = {}):
        logger.info(f"Page reload")
        page.reload()
        PlaywrightHelper.wait_for_page_load(page, browser_config)


    @staticmethod
    def restore(page: Page, url: str, browser_config: dict = {}):
        if page.url != url:
            logger.info(f"Page restores url: {url}")
            PlaywrightHelper.navigate(page, url, browser_config)
        else:
            logger.info(f"Page already on url: {url}")


    @staticmethod
    def wait_for_page_load(page: Page, browser_config: dict = {}):
        sleep_after_onload = browser_config.get("sleep_after_onload", 5) # sleep after onload
        wait_for_networkidle = browser_config.get("wait_for_networkidle", True) # wait for networkidle after onload
        timeout_networkidle = browser_config.get("timeout_networkidle", 10) # timeout for networkidle
        sleep_after_networkidle = browser_config.get("sleep_after_networkidle", 2) # sleep after networkidle
        logger.info("Waiting for page to load")
        logger.info(f"Sleeping {sleep_after_onload}s after onload")
        page.wait_for_timeout(sleep_after_onload*1000)
        if wait_for_networkidle:
            try:
                logger.info(f"Waiting {timeout_networkidle}s for networkidle")
                page.wait_for_load_state("networkidle", timeout=timeout_networkidle*1000)
                logger.info(f"Page is on networkidle, sleeping for {sleep_after_networkidle}s")
                page.wait_for_timeout(sleep_after_networkidle*1000)
            except TimeoutError:
                logger.info(f"Timeout after {timeout_networkidle}s while waiting for networkidle")
        logger.info(f"Page loaded")


    @staticmethod
    def hostname(page: Page) -> str:
        url = urlparse(page.url)
        return url.netloc


    @staticmethod
    def pathname(page: Page) -> str:
        url = urlparse(page.url)
        return url.path


    @staticmethod
    def get_content_type(page: Page) -> str:
        ct = page.evaluate("document.contentType")
        if type(ct) == str: return ct
        else: return ""


    @staticmethod
    def get_content_analyzable(page: Page) -> Tuple[bool, str]:
        # playwright bug: .locator and .evaluate hangs on about:blank pages
        if page.url == "about:blank": return False, "page is about:blank"
        # content type: html
        ct = page.evaluate("document.contentType")
        if type(ct) != str: return False, "could not determine content type of page"
        if "html" not in ct.lower(): return False, "content type of page is not html"
        return True, ""


    @staticmethod
    def set_about_blank(page: Page, sleep: int = 0):
        logger.info(f"Page loads about:blank and sleeps {sleep}s")
        page.goto("about:blank")
        page.wait_for_timeout(sleep*1000)


    @staticmethod
    def take_screenshot(page: Page) -> str:
        logger.info(f"Taking b64encoded and compressed screenshot of page")
        s = base64.b64encode(zlib.compress(page.screenshot(), 9)).decode()
        logger.info(f"Took b64encoded and compressed screenshot of page")
        return s


    @staticmethod
    def take_har(har_file: str) -> str:
        try:
            with open(har_file, "rb") as f:
                return base64.b64encode(zlib.compress(f.read(), 9)).decode()
        except FileNotFoundError:
            return ""


    @staticmethod
    def take_storage_state(context: BrowserContext) -> dict:
        logger.info(f"Taking storage state of browser context")
        return context.storage_state()


    @staticmethod
    def close_all_other_pages(page: Page):
        logger.info("Closing all pages except current page")
        for i, p in enumerate(page.context.pages):
            if p != page:
                logger.info(f"Closing page {i}")
                p.close()
                logger.info(f"Page {i} closed")


    @staticmethod
    def blank_and_close_all_other_pages(page: Page):
        logger.info("Blanking and closing all pages except current page")
        for i, p in enumerate(page.context.pages):
            if p != page:
                logger.info(f"Blanking page {i}")
                p.goto("about:blank", timeout=30_000) # throws after 30s
                logger.info(f"Closing page {i}")
                p.close()
                logger.info(f"Page {i} closed")


    @staticmethod
    def close_context(context: BrowserContext):
        # playwright bug: sometimes hangs on context close
        logger.info("Closing browser context")
        empty_page = context.new_page()
        for p in context.pages:
            if p != empty_page:
                logger.info("Blanking page")
                p.goto("about:blank", timeout=30_000) # throws after 30s
                logger.info("Closing page")
                p.close()
                logger.info("Page closed")
        logger.info(f"Closing browser context")
        context.close()
        logger.info(f"Browser context closed")


class PlaywrightBrowser:


    EXT_DIR = Path(__file__).parent / "extensions"
    JS_DIR = Path(__file__).parent / "js"


    @staticmethod
    def instance(
        playwright: Playwright,
        browser_config: dict,
        user_data_dir: str,
        har_file: str = None
    ) -> Tuple[BrowserContext, Page]:
        return PlaywrightBrowser.browser(
            playwright,
            user_data_dir=user_data_dir,
            har_file=har_file,
            browser_name=browser_config["name"],
            user_agent=browser_config["user_agent"],
            locale=browser_config["locale"],
            headless=browser_config["headless"],
            screen_width=browser_config["width"],
            screen_height=browser_config["height"],
            viewport_width=browser_config["width"],
            viewport_height=browser_config["height"],
            extensions=browser_config["extensions"],
            scripts=browser_config["scripts"],
            timeout_default=browser_config["timeout_default"],
            timeout_navigation=browser_config["timeout_navigation"]
        )


    @staticmethod
    def browser(
        playwright: Playwright,
        user_data_dir: str = f"/tmp/playwright-{uuid4()}",
        har_file: str|None = None,
        browser_name: str = "CHROMIUM",
        user_agent: str = "",
        locale: str = "en-US",
        headless: bool = False,
        screen_width: int = 1920,
        screen_height: int = 1080,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        extensions: List[str] = [],
        scripts: List[str] = [],
        timeout_default: float = 30.0,
        timeout_navigation: float = 30.0
    ) -> Tuple[BrowserContext, Page]:
        logger.info(f"Setup playwright for browser: {browser_name}")

        # browser
        if browser_name == "CHROMIUM": browser = playwright.chromium
        elif browser_name == "FIREFOX": browser = playwright.firefox
        elif browser_name == "WEBKIT": browser = playwright.webkit
        else: raise Exception(f"Browser {browser_name} is not supported")

        # extensions
        extensions_paths = []
        for e in extensions:
            if os.path.isdir(f"{PlaywrightBrowser.EXT_DIR / e}"):
                extensions_paths.append(f"{PlaywrightBrowser.EXT_DIR / e}")

        # config (browser-independent)
        kwargs = {}
        kwargs["accept_downloads"] = False
        kwargs["ignore_https_errors"] = True
        kwargs["bypass_csp"] = True
        kwargs["locale"] = locale
        kwargs["screen"] = {"width": screen_width, "height": screen_height}
        kwargs["viewport"] = {"width": viewport_width, "height": viewport_height}
        if user_agent: kwargs["user_agent"] = user_agent
        if har_file: kwargs["record_har_path"] = har_file

        # config (browser-dependent)
        if browser_name == "CHROMIUM":
            bargs = []
            # hide automation from websites
            bargs.append("--disable-blink-features=AutomationControlled")
            # new headless mode
            if headless: bargs.append("--headless=new")
            else: kwargs["headless"] = False
            # hardcoded extensions
            extensions_paths.append(f"{PlaywrightBrowser.EXT_DIR / 'chromium' / 'inbc-tracker'}")
            # extensions
            bargs.append(f"--disable-extensions-except={','.join(extensions_paths)}")
            bargs.append(f"--load-extension={','.join(extensions_paths)}")
            kwargs["args"] = bargs
        elif browser_name == "FIREFOX":
            # headless mode
            kwargs["headless"] = headless
            # firefox does not support extensions
        elif browser_name == "WEBKIT":
            # headless mode
            kwargs["headless"] = headless
            # webkit does not support extensions

        # context
        context = browser.launch_persistent_context(user_data_dir, **kwargs)

        # timeouts
        context.set_default_timeout(timeout_default*1000)
        context.set_default_navigation_timeout(timeout_navigation*1000)

        # permissions (only chromium and firefox)
        if browser_name == "CHROMIUM" or browser_name == "FIREFOX":
            context.grant_permissions([
                "notifications",
                "geolocation",
                # "midi",
                # "midi-sysex",
                # "camera",
                # "microphone",
                # "background-sync",
                # "ambient-light-sensor",
                # "accelerometer",
                # "gyroscope",
                # "magnetometer",
                # "accessibility-events",
                # "clipboard-read",
                # "clipboard-write",
                # "payment-handler"
            ])

        # scripts
        for s in scripts:
            if os.path.isfile(f"{PlaywrightBrowser.JS_DIR / s}"):
                context.add_init_script(path=f"{PlaywrightBrowser.JS_DIR / s}")

        # api overwrites
        context.add_init_script(script="""
            window.alert = ()=>{};
            window.confirm = ()=>{};
            window.prompt = ()=>{};
            window.print = ()=>{};
        """)

        # responsible web scanning
        # context.set_extra_http_headers({
        #     "X-Web-Scanner-Info": "https://sso-monitor.me/info"
        # })

        # page
        if context.pages: page = context.pages[0]
        else: page = context.new_page()

        return (context, page)
