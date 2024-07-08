import logging
import re
from typing import List
from playwright.sync_api import Page
from modules.locators.accessibility import AccessibilityLocator


logger = logging.getLogger(__name__)


class AccessibilitySAATLocator:


    REGEX_LENGTH = r"^\W*(?:\w+\b\W*){1,10}$"
    REGEX_FACEBOOK = r"(log\s{0,1}(in|on)|sign\s{0,1}(in|up|on)|continue|connect)\s*(with|using)\s*(facebook|fb)"


    @staticmethod
    def locate(page: Page, high_validity: bool) -> List[dict]:
        logger.info(f"Locating elements with accessibility saat locator ({'high' if high_validity else 'low'} validity)")

        if not high_validity:
            logger.info("Accessibility saat locator does not support low validity locating")
            return []

        logger.info(f"Getting element candidates")
        cdp = page.context.new_cdp_session(page)
        cdp.send("Accessibility.enable")
        cdp.send("DOM.enable")
        accessibility_tree = cdp.send("Accessibility.getFullAXTree")["nodes"]
        element_candidates = [node for node in accessibility_tree if AccessibilitySAATLocator.check_node(node)]
        logger.info(f"#{len(element_candidates)} element candidates found")

        logger.info(f"Transforming element candidates")
        elements = AccessibilityLocator.transform_element_candidates(element_candidates, cdp)
        logger.info(f"#{len(elements)} transformed element candidates found")
        cdp.detach()
        return elements


    @staticmethod
    def check_node(node: dict) -> bool:
        if node["ignored"] or "name" not in node or "value" not in node["name"] or not node["name"]["value"]:
            return False
        text_value = node["name"]["value"].lower()
        if not re.search(AccessibilitySAATLocator.REGEX_LENGTH, text_value): return False
        if re.search(AccessibilitySAATLocator.REGEX_FACEBOOK, text_value): return True
        if "fb:login_button" in text_value: return True
        return False
