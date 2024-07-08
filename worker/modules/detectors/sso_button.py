import logging
import time
from typing import List, Tuple
from playwright.sync_api import sync_playwright, Error, TimeoutError, Page
from config.idp_rules import IdpRules
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.tmp import TmpHelper
from modules.helper.image import ImageHelper
from modules.helper.detection import DetectionHelper
from modules.helper.pattern import PatternHelper
from modules.locators.css import CSSLocator
from modules.locators.xpath import XPathLocator
from modules.locators.accessibility import AccessibilityLocator
from modules.locators.accessibility_saat import AccessibilitySAATLocator
from modules.locators.pattern import PatternLocator


logger = logging.getLogger(__name__)


class SSOButtonDetector:


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result

        self.browser_config = config["browser_config"]
        self.artifacts_config = config["artifacts_config"]
        self.idp_scope = config["idp_config"]["idp_scope"]
        self.recognition_mode = config["recognition_strategy_config"]["recognition_mode"]
        self.recognition_strategy_scope = config["recognition_strategy_config"]["recognition_strategy_scope"]
        self.keyword_max_elements_to_click = config["keyword_recognition_config"]["max_elements_to_click"]
        self.keywords = config["keyword_recognition_config"]["keywords"]
        self.xpath = config["keyword_recognition_config"]["xpath"]
        self.logo_max_elements_to_click = config["logo_recognition_config"]["max_elements_to_click"]
        self.logo_size = config["logo_recognition_config"]["logo_size"]
        self.store_idp_har = config["artifacts_config"]["store_idp_har"]
        self.store_idp_screenshot = config["artifacts_config"]["store_idp_screenshot"]
        self.store_sso_button_detection_screenshot = config["artifacts_config"]["store_sso_button_detection_screenshot"]

        self.login_page_candidates = result["login_page_candidates"]
        self.recognized_idps = result["recognized_idps"]

        self.pattern_locator = PatternLocator(
            config["logo_recognition_config"]["max_matching"],
            config["logo_recognition_config"]["upper_bound"],
            config["logo_recognition_config"]["lower_bound"],
            config["logo_recognition_config"]["scale_upper_bound"],
            config["logo_recognition_config"]["scale_lower_bound"],
            config["logo_recognition_config"]["scale_method"],
            config["logo_recognition_config"]["scale_space"],
            config["logo_recognition_config"]["scale_order"],
            config["logo_recognition_config"]["match_intensity"],
            config["logo_recognition_config"]["match_algorithm"]
        )


    def start(self):
        logger.info(f"Starting sso button detection")

        # targets: login page candidates and idps
        lpcs_with_idps = {} # {"url1": ["idp1", "idp2", ...], ...}

        # update login page candidates based on recognition mode
        DetectionHelper.get_lpcs_with_idps(
            lpcs_with_idps, self.login_page_candidates, self.recognized_idps,
            self.recognition_mode, self.idp_scope, False
        )
        logger.info(f"Login page candidates: {lpcs_with_idps}")

        # iterate over login page candidates
        for lpc in lpcs_with_idps:
            logger.info(f"Starting sso button detection on: {lpc}")

            # check if login page candidate is reachable
            reachable = (DetectionHelper
                .get_lpc_from_url(lpc, self.login_page_candidates)
                .get("resolved", {})
                .get("reachable", False))
            if not reachable:
                logger.info(f"Login page candidate is not reachable")
                continue

            # check if login page candidate is analyzable
            valid = (DetectionHelper
                .get_lpc_from_url(lpc, self.login_page_candidates)
                .get("content_analyzable", {})
                .get("valid", False))
            if not valid:
                logger.info(f"Login page candidate is not analyzable")
                continue

            # update idps based on recognition mode
            DetectionHelper.get_lpcs_with_idps(
                lpcs_with_idps, self.login_page_candidates, self.recognized_idps,
                self.recognition_mode, self.idp_scope, True
            )
            logger.info(f"Idps: {lpcs_with_idps[lpc]}")

            # iterate over idps
            for idp in lpcs_with_idps[lpc]:
                logger.info(f"Starting sso button detection for idp {idp} on: {lpc}")

                # open browser
                with TmpHelper.tmp_dir() as pdir, TmpHelper.tmp_file() as har, sync_playwright() as pw:
                    context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir, har_file=har)

                    try:
                        # navigate to login page candidate
                        PlaywrightHelper.navigate(page, lpc, self.browser_config)

                        # content analyzable
                        valid, error = PlaywrightHelper.get_content_analyzable(page)
                        if not valid:
                            logger.info(f"Login page candidate is not analyzable: {error}")
                            PlaywrightHelper.close_context(context)
                            continue

                        # recognized idp
                        sso, sso_info = False, None

                        # iterate over detection strategies
                        for rs in self.recognition_strategy_scope:

                            # stop if sso was detected by previous detection strategy
                            if sso: break

                            # select approriate detection strategy
                            if rs == "KEYWORD-CSS":
                                t = time.time()
                                sso, sso_info = self.keyword_detection(page, lpc, idp, "CSS")
                                if "sso_button_detection_keyword_css_duration_seconds" not in self.result["timings"]:
                                    self.result["timings"]["sso_button_detection_keyword_css_duration_seconds"] = 0
                                self.result["timings"][f"sso_button_detection_keyword_css_duration_seconds"] += time.time() - t
                            elif rs == "KEYWORD-XPATH":
                                t = time.time()
                                sso, sso_info = self.keyword_detection(page, lpc, idp, "XPATH")
                                if "sso_button_detection_keyword_xpath_duration_seconds" not in self.result["timings"]:
                                    self.result["timings"]["sso_button_detection_keyword_xpath_duration_seconds"] = 0
                                self.result["timings"][f"sso_button_detection_keyword_xpath_duration_seconds"] += time.time() - t
                            elif rs == "KEYWORD-ACCESSIBILITY":
                                t = time.time()
                                sso, sso_info = self.keyword_detection(page, lpc, idp, "ACCESSIBILITY")
                                if "sso_button_detection_keyword_accessibility_duration_seconds" not in self.result["timings"]:
                                    self.result["timings"]["sso_button_detection_keyword_accessibility_duration_seconds"] = 0
                                self.result["timings"][f"sso_button_detection_keyword_accessibility_duration_seconds"] += time.time() - t
                            elif rs == "KEYWORD-ACCESSIBILITYSAAT":
                                t = time.time()
                                sso, sso_info = self.keyword_detection(page, lpc, idp, "ACCESSIBILITYSAAT")
                                if "sso_button_detection_keyword_accessibilitysaat_duration_seconds" not in self.result["timings"]:
                                    self.result["timings"]["sso_button_detection_keyword_accessibilitysaat_duration_seconds"] = 0
                                self.result["timings"][f"sso_button_detection_keyword_accessibilitysaat_duration_seconds"] += time.time() - t
                            elif rs == "LOGO":
                                t = time.time()
                                sso, sso_info = self.logo_detection(page, lpc, idp)
                                if "sso_button_detection_logo_duration_seconds" not in self.result["timings"]:
                                    self.result["timings"]["sso_button_detection_logo_duration_seconds"] = 0
                                self.result["timings"]["sso_button_detection_logo_duration_seconds"] += time.time() - t

                        # close browser to save har
                        PlaywrightHelper.close_context(context)

                        # save har
                        if sso and self.store_idp_har:
                            sso_info["idp_har"] = PlaywrightHelper.take_har(har)

                        # save recognized idp
                        if sso:
                            self.recognized_idps.append(sso_info)
                        else:
                            pass # todo: also save unrecognized idps

                    except TimeoutError as e:
                        logger.warning(f"Timeout in sso button detection for idp {idp} on: {lpc}")
                        logger.debug(e)

                    except Error as e:
                        logger.warning(f"Error in sso button detection for idp {idp} on: {lpc}")
                        logger.debug(e)


    def keyword_detection(self, page: Page, lpc: str, idp: str, locator_mode: str) -> Tuple[bool, dict]:
        logger.info(f"Starting sso button keyword detection with {locator_mode} locator for idp {idp} on: {lpc}")

        # time of keyword detection
        t = time.time()

        # locators
        if locator_mode == "CSS":
            locator = CSSLocator(IdpRules[idp]["keywords"], self.keywords)
        elif locator_mode == "XPATH":
            locator = XPathLocator(IdpRules[idp]["keywords"], self.keywords, self.xpath)
        elif locator_mode == "ACCESSIBILITY":
            locator = AccessibilityLocator(IdpRules[idp]["keywords"], self.keywords)
        elif locator_mode == "ACCESSIBILITYSAAT":
            locator = AccessibilitySAATLocator()
            if idp != "FACEBOOK": return False, None # accessibilitysaat only for facebook
        else:
            raise ValueError(f"Unsupported locator mode: {locator_mode}")

        # recognized idp
        sso, sso_info = False, None

        # high validity
        logger.info(f"Starting sso button keyword detection with high validity")
        high_validity_elements = locator.locate(page, high_validity=True)
        if high_validity_elements:
            sso, sso_info = self.check_element_matches(page, idp, locator_mode, high_validity_elements)
            if sso: # sso found with high validity
                sso_info["element_validity"] = "HIGH"
                sso_info["login_page_url"] = lpc
                sso_info["keyword_recognition_duration_seconds"] = time.time() - t

        # low validity
        if not sso: # only if sso not found with high validity
            logger.info(f"Starting sso button keyword detection with low validity")
            low_validity_elements = locator.locate(page, high_validity=False)
            if low_validity_elements:
                sso, sso_info = self.check_element_matches(page, idp, locator_mode, low_validity_elements)
                if sso: # sso found with low validity
                    sso_info["element_validity"] = "LOW"
                    sso_info["login_page_url"] = lpc
                    sso_info["keyword_recognition_duration_seconds"] = time.time() - t

        return sso, sso_info


    def logo_detection(self, page: Page, lpc: str, idp: str) -> Tuple[bool, dict]:
        logger.info(f"Starting sso button logo detection for idp {idp} on: {lpc}")

        # time of logo detection
        ts_total = time.time()

        # screenshot of login page candidate
        screenshot = page.screenshot()

        # recognized idp
        sso, sso_info = False, None

        # locate patterns on screenshot
        ts_pattern_matching = time.time()
        patterns = PatternHelper.get_patterns_of_idp(self.logo_size, idp)
        pattern_matches = self.pattern_locator.locate(screenshot, patterns)
        te_pattern_matching = time.time() - ts_pattern_matching
        if pattern_matches:
            ts_pattern_checking = time.time()
            sso, sso_info = self.check_pattern_matches(page, idp, pattern_matches)
            te_pattern_checking = time.time() - ts_pattern_checking
            if sso: # sso found
                sso_info["login_page_url"] = lpc
                sso_info["logo_recognition_pattern_matching_duration_seconds"] = te_pattern_matching
                sso_info["logo_recognition_pattern_checking_duration_seconds"] = te_pattern_checking
                sso_info["logo_recognition_duration_seconds"] = time.time() - ts_total

        return sso, sso_info


    def check_element_matches(self, page: Page, idp: str, locator_mode: str, elements: List[dict]) -> Tuple[bool, dict]:
        logger.info(f"Checking {len(elements)} element matches for sso with {idp} on: {page.url}")
        page_screenshot = PlaywrightHelper.take_screenshot(page)
        for i, element in enumerate(elements):
            logger.info(f"Checking element match {i+1} of {len(elements)}")
            if i >= self.keyword_max_elements_to_click:
                logger.info(f"Maximum click limit reached, skip remaining element matches")
                break
            element_tree, element_tree_markup = DetectionHelper.get_coordinate_metadata(
                page, element["x"] + element["width"] / 2, element["y"] + element["height"] / 2
            )
            if locator_mode == "ACCESSIBILITYSAAT": # accessibility saat locator
                logger.info("ACCESSIBILITYSAAT locator skips click on coordinate and check url")
                match, match_url, match_popup, _, match_screenshot = True, None, None, None, None
            else: # all other locators
                pre_click_url = page.url
                match, match_url, match_popup, _, match_screenshot = DetectionHelper.click_coordinate_check_url(
                    page,
                    self.browser_config,
                    (element["x"] + element["width"] / 2, element["y"] + element["height"] / 2),
                    IdpRules[idp]["login_request_rule"]["domain"],
                    IdpRules[idp]["login_request_rule"]["path"],
                    IdpRules[idp]["login_request_rule"]["params"]
                )
                PlaywrightHelper.blank_and_close_all_other_pages(page) # cleanup popups
                PlaywrightHelper.restore(page, pre_click_url, self.browser_config) # cleanup page
            if match: # sso found
                return (True, {
                    "idp_name": idp,
                    "idp_login_request": match_url,
                    "idp_frame": "POPUP" if match_popup else "TOPMOST",
                    "idp_screenshot": match_screenshot if match_screenshot and self.store_idp_screenshot else None,
                    "element_coordinates_x": element["x"],
                    "element_coordinates_y": element["y"],
                    "element_width": element["width"],
                    "element_height": element["height"],
                    "element_inner_text": element["inner_text"],
                    "element_outer_html": element["outer_html"],
                    "element_tree": element_tree,
                    "element_tree_markup": element_tree_markup,
                    "recognition_strategy": "KEYWORD",
                    "keyword_recognition_locator_mode": locator_mode,
                    "keyword_recognition_candidates": len(elements),
                    "keyword_recognition_hit_number_clicks": i + 1,
                    "keyword_recognition_hit_keyword": element["inner_text"],
                    "keyword_recognition_screenshot": ImageHelper.base64comppng_draw_rectangle(
                        page_screenshot, element["x"], element["y"], element["width"], element["height"]
                    ) if self.store_sso_button_detection_screenshot else None
                })
        return (False, None) # no sso found


    def check_pattern_matches(self, page: Page, idp: str, pattern_matches: List[dict]) -> Tuple[bool, dict]:
        logger.info(f"Checking {len(pattern_matches)} pattern matches for sso with {idp} on: {page.url}")
        page_screenshot = PlaywrightHelper.take_screenshot(page)
        for i, pattern_match in enumerate(pattern_matches):
            logger.info(f"Checking pattern match {i+1} of {len(pattern_matches)}")
            if i >= self.logo_max_elements_to_click:
                logger.info(f"Maximum click limit reached, skip remaining pattern matches")
                break
            (tf, isc, tsc, min_val, max_val, min_loc, max_loc, th, tw, ih, iw) = pattern_match.values()
            (start_x, start_y) = (int(max_loc[0] * (1/isc)), int(max_loc[1] * (1/isc)))
            (end_x, end_y) = (int((max_loc[0] + tw) * (1/isc)), int((max_loc[1] + th) * (1/isc)))
            (width, height) = (end_x - start_x, end_y - start_y)
            element_tree, element_tree_markup = DetectionHelper.get_coordinate_metadata(
                page, start_x + width / 2, start_y + height / 2
            )
            pre_click_url = page.url
            match, match_url, match_popup, _, match_screenshot = DetectionHelper.click_coordinate_check_url(
                page,
                self.browser_config,
                (start_x + width / 2, start_y + height / 2),
                IdpRules[idp]["login_request_rule"]["domain"],
                IdpRules[idp]["login_request_rule"]["path"],
                IdpRules[idp]["login_request_rule"]["params"]
            )
            PlaywrightHelper.blank_and_close_all_other_pages(page) # cleanup popups
            PlaywrightHelper.restore(page, pre_click_url, self.browser_config) # cleanup page
            if match: # sso found
                return (True, {
                    "idp_name": idp,
                    "idp_login_request": match_url,
                    "idp_frame": "POPUP" if match_popup else "TOPMOST",
                    "idp_screenshot": match_screenshot if match_screenshot and self.store_idp_screenshot else None,
                    "element_coordinates_x": start_x,
                    "element_coordinates_y": start_y,
                    "element_width": width,
                    "element_height": height,
                    "element_tree": element_tree,
                    "element_tree_markup": element_tree_markup,
                    "recognition_strategy": "LOGO",
                    "logo_recognition_candidates": len(pattern_matches),
                    "logo_recognition_hit_number_clicks": i + 1,
                    "logo_recognition_template_filename": tf,
                    "logo_recognition_template_scale": tsc,
                    "logo_recognition_screenshot_scale": isc,
                    "logo_recognition_matching_score": max_val,
                    "logo_recognition_screenshot": ImageHelper.base64comppng_draw_rectangle(
                        page_screenshot, start_x, start_y, width, height
                    ) if self.store_sso_button_detection_screenshot else None
                })
        return (False, None) # no sso found
