import logging
from typing import List
from playwright.sync_api import Error, TimeoutError, Locator, ElementHandle


logger = logging.getLogger(__name__)


class LocatorHelper:


    @staticmethod
    def get_element_metadata(
        element: Locator|ElementHandle,
        exclude_tags: List[str] = [],
        check_visible: bool = True,
        timeout: float = 5
    ):
        try:
            # exclude tags
            if exclude_tags:
                logger.info("Checking tag name of element")
                tag_name = element.evaluate("e => e.tagName")
                logger.info(f"Tag name: {tag_name}")
                if type(tag_name) != str or tag_name.lower() in exclude_tags:
                    logger.info(f"Tag name of element is in tags to exclude")
                    return (False, None, None)
            # visible
            if check_visible and not element.is_visible():
                logger.info("Element is not visible")
                return (False, None, None)
            # bounding box
            logger.info("Checking bounding box of element")
            if type(element) == Locator:
                bbox = element.bounding_box(timeout=timeout*1000)
            elif type(element) == ElementHandle:
                bbox = element.bounding_box()
            else:
                raise ValueError(f"Element is not Locator or ElementHandle but {type(element)}")
            logger.info(f"Bounding box: {bbox}")
            if not bbox:
                logger.info(f"Could not determine bounding box of element")
                return (False, None, None)
            if (
                "x" not in bbox or "y" not in bbox
                or "width" not in bbox or "height" not in bbox
            ):
                logger.info(f"Bounding box of element is missing x, y, width, or height")
                return (False, None, None)
            # inner text
            logger.info("Checking inner text of element")
            if type(element) == Locator:
                itxt = element.inner_text(timeout=timeout*1000)
            elif type(element) == ElementHandle:
                itxt = element.inner_text()
            else:
                raise ValueError(f"Element is not Locator or ElementHandle but {type(element)}")
            if type(itxt) != str:
                logger.info(f"Inner text of element is not string but {type(itxt)}: {itxt}")
                itxt = ""
            logger.info(f"Extract from inner text (total: {len(itxt)} chars): {itxt[:20]}")
            # outer html
            logger.info("Checking outer html of element")
            if type(element) == Locator:
                ohtml = element.evaluate("e => e.outerHTML", timeout=timeout*1000)
            elif type(element) == ElementHandle:
                ohtml = element.evaluate("e => e.outerHTML")
            else:
                raise ValueError(f"Element is not Locator or ElementHandle but {type(element)}")
            if type(ohtml) != str:
                logger.info(f"Outer html of element is not string but {type(ohtml)}: {ohtml}")
                ohtml = ""
            logger.info(f"Extract from outer html (total: {len(ohtml)} chars): {ohtml[:20]}")
            # result
            return (True, element, {
                "x": bbox["x"], "y": bbox["y"],
                "width": bbox["width"], "height": bbox["height"],
                "inner_text": itxt, "outer_html": ohtml
            })
        except TimeoutError as e:
            logger.info("Timeout while checking element")
            logger.debug(e)
            return (False, None, None)
        except Error as e:
            logger.info(f"Error while checking element")
            logger.debug(e)
            return (False, None, None)
