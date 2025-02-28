import logging
from playwright.sync_api import sync_playwright, Error, TimeoutError
from modules.helper.tmp import TmpHelper
from modules.browser.browser import PlaywrightBrowser, PlaywrightHelper
from modules.helper.url import URLHelper
from modules.helper.detection import DetectionHelper
from modules.locators.anchor import AnchorLocator
from modules.locators.css import CSSLocator


logger = logging.getLogger(__name__)


class Crawling:


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result

        self.browser_config = config["browser_config"]
        self.login_page_url_regexes = config["login_page_config"]["login_page_url_regexes"]
        self.login_page_element_keywords = config["login_page_config"]["login_page_element_keywords"]
        self.max_anchor_candidates = config["login_page_config"]["crawling_strategy_config"]["max_anchor_candidates"]
        self.max_element_candidates = config["login_page_config"]["crawling_strategy_config"]["max_element_candidates"]
        self.max_elements_to_click = config["login_page_config"]["crawling_strategy_config"]["max_elements_to_click"]

        self.resolved_url = result["resolved"]["url"]


    def start(self):
        logger.info(f"Starting crawling login page detection for url: {self.resolved_url}")

        with TmpHelper.tmp_dir() as pdir, sync_playwright() as pw:
            context, page = PlaywrightBrowser.instance(pw, self.browser_config, pdir)
            try:
                PlaywrightHelper.navigate(page, self.resolved_url, self.browser_config)

                # get all anchor candidates matching one of the login page url regexes
                logger.info(f"Searching all anchor candidates for login page url regexes on url: {self.resolved_url}")
                anchor_candidates = AnchorLocator.locate(page, [r["regex"] for r in self.login_page_url_regexes])
                logger.info(f"Found {len(anchor_candidates)} anchor candidates on url: {self.resolved_url}")

                # filter and prioritize anchor candidates
                logger.info(f"Filter and prioritize anchor candidates on url: {self.resolved_url}")
                anchors = []
                for i, ac in enumerate(anchor_candidates):
                    logger.info(f"Checking anchor candidate {i+1} of {len(anchor_candidates)}: {ac['href_absolute']}")

                    # check if href is on same tld as resolved url
                    if not URLHelper.is_same_tld(self.resolved_url, ac["href_absolute"]):
                        logger.info(f"Anchor candidate {i+1} of {len(anchor_candidates)} is on different tld")
                        continue

                    # determine priority of anchor candidate
                    priority = URLHelper.prio_of_url(ac["href_absolute"], self.login_page_url_regexes)

                    # store anchor as login page candidate
                    anchors.append({
                        "login_page_candidate": URLHelper.normalize(ac["href_absolute"]),
                        "login_page_strategy": "CRAWLING",
                        "login_page_locator_mode": "ANCHOR",
                        "login_page_priority": priority,
                        "login_page_info": ac
                    })

                # sort anchors by priority
                anchors = sorted(anchors, key=lambda a: a["login_page_priority"]["priority"], reverse=True)

                # store anchors in result
                for i, a in enumerate(anchors):
                    if i < self.max_anchor_candidates: self.result["login_page_candidates"].append(a)
                    # else: self.result["additional_login_page_candidates"].append(a)

                # get all element candidates matching one of the login page element keywords
                logger.info(f"Searching all element candidates for login page element keywords on url: {self.resolved_url}")
                element_candidates = CSSLocator(self.login_page_element_keywords).locate(page, high_validity=False)
                logger.info(f"Found {len(element_candidates)} element candidates on url: {self.resolved_url}")

                # click, filter, and prioritize element candidates
                elements = []
                for i, e in enumerate(element_candidates[:self.max_elements_to_click]):
                    logger.info(f"Clicking on element candidate {i+1} of {len(element_candidates)}")
                    pre_click_url = page.url

                    # get element tree of element candidate
                    element_tree, element_tree_markup = DetectionHelper.get_coordinate_metadata(
                        page, e["x"] + e["width"]/2, e["y"] + e["height"]/2
                    )

                    # click on element candidate
                    try:
                        with page.expect_popup(timeout=2_000) as page_info:
                            logger.info("Clicking on coordinate of element candidate and waiting for popup")
                            page.mouse.click(e["x"] + e["width"]/2, e["y"] + e["height"]/2)
                        logger.info("Popup opened after clicking coordinate, waiting for popup to load")
                        PlaywrightHelper.wait_for_page_load(page_info.value, self.browser_config)
                        post_click_url = page_info.value.url
                        post_click_frame = "POPUP"
                    except TimeoutError:
                        logger.info("No popup opened after clicking coordinate, waiting for page to load")
                        PlaywrightHelper.wait_for_page_load(page, self.browser_config)
                        post_click_url = page.url
                        post_click_frame = "TOPMOST"
                    except Error:
                        logger.info("Popup immediately closed after opening, could not wait for page to load")
                        continue
                    finally:
                        logger.info(f"Restoring page to pre click state")
                        PlaywrightHelper.blank_and_close_all_other_pages(page)
                        if page.url != pre_click_url: PlaywrightHelper.navigate(page, pre_click_url, self.browser_config)

                    # click on element navigates to different url
                    if pre_click_url != post_click_url:
                        logger.info(f"Clicking on coordinate navigates to different url in {post_click_frame}: {post_click_url}")

                        # check if post click url is on same tld as resolved url
                        if not URLHelper.is_same_tld(pre_click_url, post_click_url):
                            logger.info(f"Post click url is on different tld")
                            continue

                        # avoid duplicate post click urls
                        if any([e["login_page_candidate"] == post_click_url for e in elements]):
                            logger.info(f"Post click url is a duplicate")
                            continue

                        # consider post click urls of any priority because we clicked on an item with "login" keyword
                        priority = URLHelper.prio_of_url(post_click_url, self.login_page_url_regexes)

                        # store element as login page candidate
                        elements.append({
                            "login_page_candidate": URLHelper.normalize(post_click_url),
                            "login_page_strategy": "CRAWLING",
                            "login_page_locator_mode": "ELEMENT",
                            "login_page_priority": priority,
                            "login_page_info": {
                                **e,
                                "login_page_frame": post_click_frame,
                                "element_tree": element_tree,
                                # "element_tree_markup": element_tree_markup
                            }
                        })

                    # click on element does not navigate to different url
                    else:
                        logger.info(f"Clicking on coordinate does not navigate to different url")

                # sort elements by priority
                elements = sorted(elements, key=lambda e: e["login_page_priority"]["priority"], reverse=True)

                # store elements in result
                for i, e in enumerate(elements):
                    if i < self.max_element_candidates: self.result["login_page_candidates"].append(e)
                    # else: self.result["additional_login_page_candidates"].append(e)

                PlaywrightHelper.close_context(context)
            except TimeoutError as e:
                logger.warning(f"Timeout while crawling: {self.resolved_url}")
                logger.debug(e)
            except Error as e:
                logger.warning(f"Error while crawling: {self.resolved_url}")
                logger.debug(e)
