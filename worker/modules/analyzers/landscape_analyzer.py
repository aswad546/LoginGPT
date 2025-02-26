import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Error, TimeoutError
from config.idp_rules import IdpRules
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.tmp import TmpHelper
from modules.helper.detection import DetectionHelper
from modules.helper.url import URLHelper
from modules.loginpagedetection.paths import Paths
from modules.loginpagedetection.sitemap import Sitemap
from modules.loginpagedetection.robots import Robots
from modules.loginpagedetection.searxng import Searxng
from modules.loginpagedetection.crawling_llm import Crawling
from modules.detectors.sso_button import SSOButtonDetector
from modules.detectors.request import RequestDetector
from modules.detectors.lastpass_icon import LastpassIconDetector
from modules.detectors.metadata import MetadataDetector
from modules.detectors.navigator_credentials import NavigatorCredentialsDetector


logger = logging.getLogger(__name__)


class LandscapeAnalyzer:


    def __init__(self, domain: str, config: dict):
        self.domain = domain
        self.config = config

        self.browser_config = config["browser_config"]
        self.artifacts_config = config["artifacts_config"]
        self.login_page_url_regexes = config["login_page_config"]["login_page_url_regexes"]
        self.recognition_strategy_scope = config["recognition_strategy_config"]["recognition_strategy_scope"]
        self.login_page_strategy_scope = config["login_page_config"]["login_page_strategy_scope"]

        self.result = {}
        self.result["resolved"] = {}
        self.result["timings"] = {}
        self.result["login_page_candidates"] = []
        # self.result["additional_login_page_candidates"] = []
        self.result["recognized_idps"] = []
        self.result["recognized_idps_passive"] = []
        self.result["recognized_navcreds"] = []
        self.result["recognized_lastpass_icons"] = []


    def start(self) -> dict:
        logger.info(f"Starting landscape analysis for domain: {self.domain}")

        ttotal = time.time()

        # resolve
        t = time.time()
        self.resolve()
        self.result["timings"]["resolve_duration_seconds"] = time.time() - t

        # login page detection
        if self.result["resolved"]["reachable"]:
            t = time.time()
            self.login_page_detection_parallel()
            self.result["timings"]["login_page_detection_duration_seconds"] = time.time() - t

        # login page analysis
        if self.result["resolved"]["reachable"]:
            t = time.time()
            self.login_page_analysis()
            self.result["timings"]["login_page_analysis_duration_seconds"] = time.time() - t

        # # sso button detection
        # if self.result["resolved"]["reachable"]:
        #     t = time.time()
        #     SSOButtonDetector(self.config, self.result).start()
        #     self.result["timings"]["sso_button_detection_duration_seconds"] = time.time() - t

        # # merge recognized_idps_passive into recognized_idps
        # self.result["recognized_idps"].extend(self.result["recognized_idps_passive"])
        # del self.result["recognized_idps_passive"]

        # # sdk detection
        # if self.result["resolved"]["reachable"]:
        #     t = time.time()
        #     self.sdk_detection()
        #     self.result["timings"]["sdk_detection_duration_seconds"] = time.time() - t

        # # metadata detection
        # if self.result["resolved"]["reachable"] and "METADATA" in self.recognition_strategy_scope:
        #     t = time.time()
        #     MetadataDetector(self.config, self.result).start()
        #     self.result["timings"]["metadata_detection_duration_seconds"] = time.time() - t

        self.result["timings"]["total_duration_seconds"] = time.time() - ttotal

        return self.result


    def resolve(self):
        logger.info(f"Starting resolve for domain: {self.domain}")

        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)

            try:
                logger.info(f"Resolving https://{self.domain}")
                r = page.goto(f"https://{self.domain}")
                s, u = r.status if r else None, page.url
                if not s or s < 200 or s >= 400: # status code 2xx or 3xx
                    logger.info(f"Invalid status code while resolving domain {self.domain} with https: {s}")
                else:
                    logger.info(f"Successfully resolved domain {self.domain} with https: {u}")
                    self.result["resolved"] = {"reachable": True, "domain": urlparse(u).netloc, "url": u}
                    return
            except TimeoutError as e:
                logger.info(f"Timeout while resolving domain {self.domain} with https")
                logger.debug(e)
            except Error as e:
                logger.info(f"Error while resolving domain {self.domain} with https")
                logger.debug(e)

            try:
                logger.info(f"Resolving http://{self.domain}")
                r = page.goto(f"http://{self.domain}")
                s, u = r.status if r else None, page.url
                if not s or s < 200 or s >= 400: # status code 2xx or 3xx
                    logger.info(f"Invalid status code while resolving domain {self.domain} with http: {s}")
                    self.result["resolved"] = {"reachable": False, "error_msg": f"Status code {s}"}
                else:
                    logger.info(f"Successfully resolved domain {self.domain} with http: {u}")
                    self.result["resolved"] = {"reachable": True, "domain": urlparse(u).netloc, "url": u}
            except TimeoutError as e:
                logger.info(f"Timeout while resolving domain {self.domain} with http")
                logger.debug(e)
                self.result["resolved"] = {"reachable": False, "error_msg": "Timeout", "error": traceback.format_exc()}
            except Error as e:
                logger.info(f"Error while resolving domain {self.domain} with http")
                logger.debug(e)
                self.result["resolved"] = {"reachable": False, "error_msg": f"{e}", "error": traceback.format_exc()}

    def _detect_homepage(self):
        t = time.time()
        lpc = self.result["resolved"]["url"]
        self.result["login_page_candidates"].append({
            "login_page_candidate": URLHelper.normalize(lpc),
            "login_page_strategy": "HOMEPAGE",
            "login_page_priority": URLHelper.prio_of_url(lpc, self.login_page_url_regexes)
        })
        duration = time.time() - t
        return {"login_page_detection_homepage_duration_seconds": duration}

    def _detect_manual(self):
        t = time.time()
        for lpc in self.config["login_page_config"]["manual_strategy_config"]["login_page_candidates"]:
            self.result["login_page_candidates"].append({
                "login_page_candidate": URLHelper.normalize(lpc),
                "login_page_strategy": "MANUAL",
                "login_page_priority": URLHelper.prio_of_url(lpc, self.login_page_url_regexes)
            })
        duration = time.time() - t
        return {"login_page_detection_manual_duration_seconds": duration}

    def _detect_crawling(self):
        t = time.time()
        Crawling(self.config, self.result, self.domain).start()
        duration = time.time() - t
        return {"login_page_detection_crawling_duration_seconds": duration}

    def _detect_paths(self):
        t = time.time()
        Paths(self.config, self.result).start()
        duration = time.time() - t
        return {"login_page_detection_paths_duration_seconds": duration}

    def _detect_sitemap(self):
        t = time.time()
        Sitemap(self.config, self.result).start()
        duration = time.time() - t
        return {"login_page_detection_sitemap_duration_seconds": duration}

    def _detect_robots(self):
        t = time.time()
        Robots(self.config, self.result).start()
        duration = time.time() - t
        return {"login_page_detection_robots_duration_seconds": duration}

    def _detect_metasearch(self):
        t = time.time()
        Searxng(self.config, self.result).start()
        duration = time.time() - t
        return {"login_page_detection_metasearch_duration_seconds": duration}

    def login_page_detection_parallel(self):
        logger.info(f"Starting parallel login page detection for domain: {self.domain}")
        strategy_functions = []

        for lps in self.login_page_strategy_scope:
            if lps == "HOMEPAGE":
                strategy_functions.append(self._detect_homepage)
            elif lps == "MANUAL":
                strategy_functions.append(self._detect_manual)
            elif lps == "PATHS":
                strategy_functions.append(self._detect_paths)
            elif lps == "CRAWLING":
                strategy_functions.append(self._detect_crawling)
            elif lps == "SITEMAP":
                strategy_functions.append(self._detect_sitemap)
            elif lps == "ROBOTS":
                strategy_functions.append(self._detect_robots)
            elif lps == "METASEARCH":
                strategy_functions.append(self._detect_metasearch)

        # Run all strategies concurrently using a thread pool
        timings = {}
        with ThreadPoolExecutor(max_workers=len(strategy_functions)) as executor:
            futures = [executor.submit(fn) for fn in strategy_functions]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    timings.update(result)
                except Exception as e:
                    logger.error("Error in detection strategy: " + str(e))
        # Merge collected timings into self.result["timings"]
        self.result["timings"].update(timings)


    def login_page_detection(self):
        logger.info(f"Starting login page detection for domain: {self.domain}")

        for lps in self.login_page_strategy_scope:

            # strategy: homepage (resolved url)
            if lps == "HOMEPAGE":
                t = time.time()
                lpc = self.result["resolved"]["url"]
                self.result["login_page_candidates"].append({
                    "login_page_candidate": URLHelper.normalize(lpc),
                    "login_page_strategy": "HOMEPAGE",
                    "login_page_priority": URLHelper.prio_of_url(lpc, self.login_page_url_regexes)
                })
                self.result["timings"]["login_page_detection_homepage_duration_seconds"] = time.time() - t

            # strategy: manual (manually specified urls)
            if lps == "MANUAL":
                t = time.time()
                for lpc in self.config["login_page_config"]["manual_strategy_config"]["login_page_candidates"]:
                    self.result["login_page_candidates"].append({
                        "login_page_candidate": URLHelper.normalize(lpc),
                        "login_page_strategy": "MANUAL",
                        "login_page_priority": URLHelper.prio_of_url(lpc, self.login_page_url_regexes)
                    })
                self.result["timings"]["login_page_detection_manual_duration_seconds"] = time.time() - t

            # strategy: paths (well-known paths and subdomains)
            if lps == "PATHS":
                t = time.time()
                Paths(self.config, self.result).start()
                self.result["timings"]["login_page_detection_paths_duration_seconds"] = time.time() - t

            # strategy: crawling (crawls on homepage)
            if lps == "CRAWLING":
                t = time.time()
                Crawling(self.config, self.result, self.domain).start()
                self.result["timings"]["login_page_detection_crawling_duration_seconds"] = time.time() - t

            # strategy: sitemap (sitemap.xml)
            if lps == "SITEMAP":
                t = time.time()
                Sitemap(self.config, self.result).start()
                self.result["timings"]["login_page_detection_sitemap_duration_seconds"] = time.time() - t

            # strategy: robots (robots.txt)
            if lps == "ROBOTS":
                t = time.time()
                Robots(self.config, self.result).start()
                self.result["timings"]["login_page_detection_robots_duration_seconds"] = time.time() - t

            # strategy: metasearch (searxng)
            if lps == "METASEARCH":
                t = time.time()
                Searxng(self.config, self.result).start()
                self.result["timings"]["login_page_detection_metasearch_duration_seconds"] = time.time() - t


    def login_page_analysis(self):
        logger.info(f"Starting login page analysis for domain: {self.domain}")

        bconf = self.config["browser_config"]
        lpcs = self.result["login_page_candidates"]

        with TmpHelper.tmp_dir() as pdir, TmpHelper.tmp_file() as har, sync_playwright() as pw:

            # do not modify original browser config
            bconf = deepcopy(bconf)

            # add lastpass extension if needed
            if "LASTPASS_ICON" in self.recognition_strategy_scope and not any("chromium/lastpass" in e for e in bconf["extensions"]):
                bconf["extensions"].append("chromium/lastpass-v4.114.0")

            # add navcred-tracker.js if needed
            if "NAVIGATOR_CREDENTIALS" in self.recognition_strategy_scope and not "navcred-tracker.js" in bconf["scripts"]:
                bconf["scripts"].append("navcred-tracker.js")

            # open browser
            context, page = PlaywrightBrowser.instance(
                pw, bconf, pdir, har_file=har if self.artifacts_config["store_login_page_analysis_har"] else None
            )

            # request detector
            rdetector = RequestDetector(self.config, self.result, context)

            # navigator credentials detector
            navcreddetector = NavigatorCredentialsDetector(self.result, page)

            # wait for lastpass extension to initialize
            if "LASTPASS_ICON" in self.recognition_strategy_scope:
                PlaywrightHelper.set_about_blank(page, 5)
                PlaywrightHelper.close_all_other_pages(page)

            # loop over login page candidates
            for lpc_url, lpc_idxs in DetectionHelper.get_lpcs_with_idxs(lpcs):
                logger.info(f"Starting analysis of login page candidate {lpc_idxs} of {len(lpcs)}: {lpc_url}")

                try:
                    # register request detector (for 1st page load)
                    if "REQUEST" in self.recognition_strategy_scope:
                        rdetector.register_interceptor(lpc_url, False)

                    # register navigator credentials callback
                    navcreddetector.register_callback(lpc_url)

                    # load login page candidate
                    PlaywrightHelper.navigate(page, lpc_url, bconf)
                    PlaywrightHelper.sleep(page, 5)

                    # unregister request detector (for 1st page load)
                    if "REQUEST" in self.recognition_strategy_scope:
                        rdetector.unregister_interceptor()

                    # unregister navigator credentials callback
                    navcreddetector.unregister_callback(lpc_url)

                    # resolve
                    url, title = page.url, page.title()
                    for i in lpc_idxs:
                        self.result["login_page_candidates"][i]["resolved"] = {
                            "reachable": True, "domain": urlparse(url).netloc, "url": url, "title": title
                        }

                    # content type
                    ct = PlaywrightHelper.get_content_type(page)
                    for i in lpc_idxs:
                        self.result["login_page_candidates"][i]["content_type"] = ct

                    # content analyzable
                    valid, error = PlaywrightHelper.get_content_analyzable(page)
                    if valid: # page is analyzable
                        logger.info(f"Login page candidate is analyzable")
                        for i in lpc_idxs:
                            self.result["login_page_candidates"][i]["content_analyzable"] = {"valid": True, "error": None}
                    else: # page is not analyzable
                        logger.info(f"Login page candidate is not analyzable: {error}")
                        for i in lpc_idxs:
                            self.result["login_page_candidates"][i]["content_analyzable"] = {"valid": False, "error": error}
                        continue # skip to next login page candidate

                    # screenshot
                    if self.artifacts_config["store_login_page_candidate_screenshot"]:
                        logger.info(f"Taking login page candidate screenshot")
                        s = PlaywrightHelper.take_screenshot(page)
                        for i in lpc_idxs:
                            self.result["login_page_candidates"][i]["login_page_candidate_screenshot"] = s

                    # loop over frames
                    for j, frame in enumerate(page.frames):
                        logger.info(f"Analyzing frame {j+1} of {len(page.frames)}: {frame.url}")

                        # content analyzable
                        valid, error = PlaywrightHelper.get_content_analyzable(frame)
                        if not valid:
                            logger.info(f"Frame is not analyzable: {error}")
                            continue # skip to next frame

                        # lastpass icon detection
                        if "LASTPASS_ICON" in self.recognition_strategy_scope:
                            t = time.time()
                            LastpassIconDetector(self.config, self.result).start(lpc_url, j, frame)
                            self.result["timings"]["lastpass_icon_detection_duration_seconds"] = time.time() - t

                    # register request detector (for 2nd page load)
                    if "REQUEST" in self.recognition_strategy_scope:
                        rdetector.register_interceptor(lpc_url, True)

                    # reload login page candidate
                    PlaywrightHelper.reload(page, bconf)
                    PlaywrightHelper.sleep(page, 5)

                    # unregister request detector (for 2nd page load)
                    if "REQUEST" in self.recognition_strategy_scope:
                        rdetector.unregister_interceptor()

                except TimeoutError as e:
                    logger.info(f"Timeout while analyzing login page candidate {lpc_idxs} of {len(lpcs)}")
                    logger.debug(e)
                    for i in lpc_idxs:
                        self.result["login_page_candidates"][i]["resolved"] = {
                            "reachable": False, "error_msg": "Timeout", "error": traceback.format_exc()
                        }

                except Error as e:
                    logger.info(f"Error while analyzing login page candidate {lpc_idxs} of {len(lpcs)}")
                    logger.debug(e)
                    for i in lpc_idxs:
                        self.result["login_page_candidates"][i]["resolved"] = {
                            "reachable": False, "error_msg": f"{e}", "error": traceback.format_exc()
                        }

            # close browser and save har
            try:
                PlaywrightHelper.close_context(context)
                if self.artifacts_config["store_login_page_analysis_har"]:
                    self.result["login_page_analysis_har"] = PlaywrightHelper.take_har(har)
            except TimeoutError as e:
                logger.info(f"Timeout while closing browser and saving har")
                logger.debug(e)
            except Error as e:
                logger.info(f"Error while closing browser and saving har")
                logger.debug(e)


    def sdk_detection(self):
        logger.info(f"Starting sdk detection for domain: {self.domain}")

        for i, idp in enumerate(self.result["recognized_idps"]):
            logger.info(f"Matching sdks of idp {i+1} of {len(self.result['recognized_idps'])}: {idp['idp_name']}")

            # fallback if no integration matches
            self.result["recognized_idps"][i]["idp_integration"] = "N/A"

            # use first integration rule that matches
            for integration, rules in IdpRules[idp["idp_name"]]["sdks"].items():
                logger.info(f"Matching login request against rule: {idp['idp_login_request']} <-> {rules['login_request_rule']}")

                if idp["idp_login_request"] and URLHelper.match_url(
                    idp["idp_login_request"],
                    rules["login_request_rule"]["domain"],
                    rules["login_request_rule"]["path"],
                    rules["login_request_rule"]["params"]
                ):
                    logger.info(f"Matched login request rule for integration: {integration}")
                    self.result["recognized_idps"][i]["idp_integration"] = integration
                    break # use first integration rule that matches
