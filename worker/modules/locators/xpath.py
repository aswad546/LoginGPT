import logging
from typing import List
from playwright.sync_api import Page
from modules.helper.locator import LocatorHelper


logger = logging.getLogger(__name__)


class XPathLocator:


    # https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes
    attributes_high_validity = [
        "title", "aria-label", "value", "id", "alt", "label", "name", "placeholder"
    ]
    attributes_low_validity = [
        "title", "aria-label", "value", "id", "alt", "label", "name", "placeholder", "class", "action", "href", "data"
    ]
    # https://developer.mozilla.org/en-US/docs/Web/HTML/Element
    tags_to_exclude = [
        "script", "html", "body", "head", "noscript"
    ]


    def __init__(
        self,
        keywords: List[str],
        high_validity_patterns: List[str] = [],
        xpath_prefixes: List[str] = ["//*"]
    ):
        # keyword to search (i.e., "google", "login", ...)
        self.keywords = [k.lower() for k in keywords]
        # high validity patterns in which %s is replaced with keyword (i.e., ["login with %s", ...])
        self.high_validity_patterns = [p.lower() for p in high_validity_patterns]

        # keywords to search for in text and attributes of elements
        self.low_validity_keywords = self.keywords
        self.high_validity_keywords = [p.replace("%s", k) for k in self.keywords for p in self.high_validity_patterns]

        # xpath locator
        self.low_validity_locator = self.get_xpath_locator(
            self.low_validity_keywords,
            self.attributes_low_validity,
            xpath_prefixes
        )
        self.high_validity_locator = self.get_xpath_locator(
            self.high_validity_keywords,
            self.attributes_high_validity,
            xpath_prefixes
        )


    def locate(self, page: Page, high_validity: bool) -> List[dict]:
        logger.info(f"Locating elements with xpath locator ({'high' if high_validity else 'low'} validity)")

        logger.info(f"Getting element candidates")
        if high_validity:
            element_candidates = page.locator(self.high_validity_locator).all()
        else:
            element_candidates = page.locator(self.low_validity_locator).all()
        logger.info(f"#{len(element_candidates)} element candidates found")

        logger.info(f"Filtering element candidates")
        elements = []
        for i, e in enumerate(element_candidates[:100]):
            logger.info(f"Checking element candidate {i+1} of {len(element_candidates)}")
            el_valid, el_loc, el_info = LocatorHelper.get_element_metadata(
                e, exclude_tags=self.tags_to_exclude
            )
            if el_valid:
                logger.info(f"Element candidate {i+1} is valid")
                elements.append(el_info)
            else:
                logger.info(f"Element candidate {i+1} is invalid")
        logger.info(f"#{len(elements)} filtered element candidates found")

        return elements


    @staticmethod
    def get_xpath_locator(keywords: List[str], attributes: List[str], xpath_prefixes: List[str], exact_match: bool = False) -> str:
        first_xpath_prefix = True
        xpath = ""
        for xpath_prefix in xpath_prefixes:
            if not first_xpath_prefix:
                xpath += " or "
            else:
                first_xpath_prefix = False
            first_search_text = True
            xpath += xpath_prefix + "["
            for text in keywords:
                if not first_search_text:
                    xpath += " or "
                if exact_match:
                    xpath += "translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', " \
                             "'abcdefghijklmnopqrstuvwxyz')='" + text.lower() + "'"
                    for i in range(50):
                        xpath += " or translate(normalize-space(text()[" + str(
                            i) + "]), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='" + text.lower() + "'"
                else:
                    xpath += "contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', " \
                             "'abcdefghijklmnopqrstuvwxyz'), '" + text.lower() + "')"
                    for i in range(50):
                        xpath += " or translate(normalize-space(text()[" + str(
                            i) + "]), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='" + text.lower() + "'"
                for attribute in attributes:
                    if exact_match:
                        xpath += " or translate(@" + attribute + \
                                 ", 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='" + text.lower() + "'"
                    else:
                        xpath += " or contains(translate(@" + attribute + \
                                 ", 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '" + text.lower() + "')"
                first_search_text = False
            xpath += "]"
        return xpath
