import re
import logging
from typing import List
from playwright.sync_api import Page
from modules.helper.locator import LocatorHelper


logger = logging.getLogger(__name__)


class AnchorLocator:


    # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/a


    @staticmethod
    def locate(page: Page, url_regexes: List[str]) -> List[dict]:
        logger.info(f"Locating anchors with anchor locator")

        logger.info(f"Getting all anchor candidates")
        anchor_candidates = page.locator("a").all()
        logger.info(f"#{len(anchor_candidates)} anchor candidates found")

        logger.info(f"Getting hrefs of anchor candidates")
        hrefs = set()
        for i, a in enumerate(anchor_candidates):
            try:
                logger.info(f"Getting href of anchor candidate {i+1} of {len(anchor_candidates)}")
                href_attr = a.get_attribute("href", timeout=1_000) # gets the href as it is
                href_abs = a.evaluate("a => a.href", timeout=1_000) # gets the href as absolute url
                logger.info(f"Anchor candidate {i+1} of {len(anchor_candidates)} href: {href_attr} | {href_abs}")
                if type(href_attr) is not str or type(href_abs) is not str:
                    logger.info(f"Anchor candidate {i+1} of {len(anchor_candidates)} has invalid href")
                    continue
                if not href_attr or not href_abs:
                    logger.info(f"Anchor candidate {i+1} of {len(anchor_candidates)} has no or invalid href")
                    continue
                if not href_abs.startswith("http://") and not href_abs.startswith("https://"):
                    logger.info(f"Anchor candidate {i+1} of {len(anchor_candidates)} href does not start with http(s)")
                    continue
                hrefs.add((href_attr, href_abs))
            except TimeoutError:
                logger.info(f"Timeout while getting href of anchor candidate {i+1} of {len(anchor_candidates)}")
        logger.info(f"#{len(hrefs)} hrefs of anchor candidates found")

        logger.info(f"Filtering hrefs of anchor candidates")
        anchors = []
        for i, href in enumerate(hrefs):
            logger.info(f"Checking href {i+1} of {len(hrefs)}")
            href_attr, href_abs = href
            for r in url_regexes:
                if re.compile(r, re.IGNORECASE).search(href_abs):
                    logger.info(f"Href {href_abs} matches regex {r}")
                    a_valid, a_loc, a_info = LocatorHelper.get_element_metadata(
                        page.locator(f'a[href="{href_attr}"]').first, check_visible=False, timeout=1
                    )
                    if a_valid:
                        logger.info(f"Href {i+1} of {len(hrefs)} is valid")
                        anchors.append({
                            **a_info,
                            "href_attribute": href_attr,
                            "href_absolute": href_abs
                        })
                    else:
                        logger.info(f"Href {i+1} of {len(hrefs)} is invalid")
                    break # add href only once if it matches arbitrary regex
        logger.info(f"#{len(anchors)} filtered hrefs of anchor candidates found")

        return anchors
