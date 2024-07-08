import logging
from typing import List
from playwright.sync_api import Frame
from modules.helper.locator import LocatorHelper
from modules.helper.detection import DetectionHelper


logger = logging.getLogger(__name__)


class LastpassIconLocator:


    @staticmethod
    def locate(frame: Frame) -> List[dict]:
        """ Locates the lastpass icon, which is injected into the username and password input fields, in a frame.
            The lastpass icon is injected into their style attributes as background image.
            Example: <input ... style="background-image: url(&quot;data:image/png;base64, ... &quot;); ...">
        """
        logger.info(f"Locating elements with lastpass icon locator")
        element_candidates = frame.locator('[style*="iVBORw0KGgoAAAANSUhEUgAAABAAAAASCAYAAABSO15qAAAAAXNSR0IArs4c6QAAAPhJREFUOBHlU70KgzAQPlMhEvoQTg6OPoOjT+JWOnRqkUKHgqWP4OQbOPokTk6OTkVULNSLVc62oJmbIdzd95NcuGjX2/3YVI/Ts+t0WLE2ut5xsQ0O+90F6UxFjAI8qNcEGONia08e6MNONYwCS7EQAizLmtGUDEzTBNd1fxsYhjEBnHPQNG3KKTYV34F8ec/zwHEciOMYyrIE3/ehKAqIoggo9inGXKmFXwbyBkmSQJqmUNe15IRhCG3byphitm1/eUzDM4qR0TTNjEixGdAnSi3keS5vSk2UDKqqgizLqB4YzvassiKhGtZ/jDMtLOnHz7TE+yf8BaDZXA509yeBAAAAAElFTkSuQmCC"]').all()
        logger.info(f"#{len(element_candidates)} element candidates found")
        logger.info(f"Checking element candidates")
        elements = []
        for i, e in enumerate(element_candidates[:100]):
            logger.info(f"Checking element candidate {i+1} of {len(element_candidates)}")
            el_valid, el_loc, el_info = LocatorHelper.get_element_metadata(e)
            if el_valid:
                logger.info(f"Element candidate {i+1} is valid")
                valid_element = {
                    "element_coordinates_x": el_info["x"],
                    "element_coordinates_y": el_info["y"],
                    "element_width": el_info["width"],
                    "element_height": el_info["height"],
                    "element_inner_text": el_info["inner_text"],
                    "element_outer_html": el_info["outer_html"]
                }
                if type(frame) == Frame and frame.parent_frame:
                    logger.info(f"Element candidate {i+1} is in iframe, calculating coordinates relative to iframe")
                    frame_valid, frame_handle, frame_info = LocatorHelper.get_element_metadata(frame.frame_element())
                    if frame_valid:
                        logger.info(f"Iframe is valid")
                        valid_element["element_frame_coordinates_x"] = frame_info["x"]
                        valid_element["element_frame_coordinates_y"] = frame_info["y"]
                        valid_element["element_frame_width"] = frame_info["width"]
                        valid_element["element_frame_height"] = frame_info["height"]
                        element_tree, element_tree_markup = DetectionHelper.get_coordinate_metadata(
                            frame,
                            el_info["x"] - frame_info["x"] + el_info["width"] / 2,
                            el_info["y"] - frame_info["y"] + el_info["height"] / 2
                        )
                        valid_element["element_tree"] = element_tree
                        valid_element["element_tree_markup"] = element_tree_markup
                    else:
                        logger.info(f"Iframe is invalid")
                        valid_element["element_tree"] = []
                        valid_element["element_tree_markup"] = []
                else:
                    logger.info(f"Element candidate {i+1} is in topmost frame")
                    element_tree, element_tree_markup = DetectionHelper.get_coordinate_metadata(
                        frame,
                        el_info["x"] + el_info["width"] / 2,
                        el_info["y"] + el_info["height"] / 2
                    )
                    valid_element["element_tree"] = element_tree
                    valid_element["element_tree_markup"] = element_tree_markup
                elements.append(valid_element)
            else:
                logger.info(f"Element candidate {i+1} is invalid")
        logger.info(f"#{len(elements)} elements found")
        return elements
