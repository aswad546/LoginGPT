import logging
from typing import List
from playwright.sync_api import Page, CDPSession, Error, TimeoutError


logger = logging.getLogger(__name__)


class AccessibilityLocator:


    def __init__(
        self,
        keyword: List[str],
        high_validity_patterns: List[str] = []
    ):
        # keyword to search (i.e., "google", "login", ...)
        self.keywords = [k.lower() for k in keyword]
        # high validity patterns in which %s is replaced with keyword (i.e., ["login with %s", ...])
        self.high_validity_patterns = [p.lower() for p in high_validity_patterns]

        # keywords to search for in text and attributes of elements
        self.low_validity_keywords = self.keywords
        self.high_validity_keywords = [p.replace("%s", k) for k in self.keywords for p in self.high_validity_patterns]


    def locate(self, page: Page, high_validity: bool) -> List[dict]:
        logger.info(f"Locating elements with accessibility locator ({'high' if high_validity else 'low'} validity)")

        logger.info(f"Getting element candidates")
        cdp = page.context.new_cdp_session(page)
        cdp.send("Accessibility.enable")
        cdp.send("DOM.enable")
        accessibility_tree = cdp.send("Accessibility.getFullAXTree")["nodes"]
        if high_validity:
            element_candidates = [node for node in accessibility_tree if self.check_node(node, self.high_validity_keywords)]
        else:
            element_candidates = [node for node in accessibility_tree if self.check_node(node, self.low_validity_keywords)]
        logger.info(f"#{len(element_candidates)} element candidates found")

        logger.info(f"Transforming element candidates")
        elements = self.transform_element_candidates(element_candidates, cdp)
        logger.info(f"#{len(elements)} transformed element candidates found")
        cdp.detach()
        return elements


    @staticmethod
    def check_node(node: dict, keywords: List[str]) -> bool:
        if node["ignored"] or "name" not in node or "value" not in node["name"] or not node["name"]["value"]:
            return False
        text_value = node["name"]["value"].lower()
        for k in keywords:
            if k in text_value:
                return True
        return False


    @staticmethod
    def transform_element_candidates(element_candidates: List[dict], cdp: CDPSession) -> List[dict]:
        elements = []
        for i, e in enumerate(element_candidates):
            try:
                logger.info(f"Transform element candidate {i+1} of {len(element_candidates)}")
                if "backendDOMNodeId" not in e or "name" not in e or "value" not in e["name"]:
                    logger.info(f"Element candidate {i+1} of {len(element_candidates)} is not valid")
                    continue
                box = cdp.send("DOM.getBoxModel", {"backendNodeId": e["backendDOMNodeId"]})
                quad = box["model"]["content"]
                rect = AccessibilityLocator.quad_to_rect(quad)
                el_info = {
                    "x": rect["x"], "y": rect["y"],
                    "width": rect["width"], "height": rect["height"],
                    "inner_text": e["name"]["value"], "outer_html": ""
                }
                logger.info(f"Element candidate {i+1} of {len(element_candidates)} is valid")
                elements.append(el_info)
            except TimeoutError as e:
                logger.info(f"Timeout while checking element candidate")
                logger.debug(e)
            except Error as e:
                logger.warning(f"Error while checking element candidate")
                logger.debug(e)
        return elements


    @staticmethod
    def quad_to_rect(quad: List[int]) -> dict:
        x_values = quad[::2]
        y_values = quad[1::2]
        x = min(x_values)
        y = min(y_values)
        width = max(x_values) - x
        height = max(y_values) - y
        return {"x": x, "y": y, "width": width, "height": height}
