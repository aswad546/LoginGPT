import logging
import imutils
import cv2
import numpy
from typing import List


logger = logging.getLogger(__name__)


class PatternLocator:


    """ Example: https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html

        match_algorithm:
            cv::TM_SQDIFF = 0, (minimum value gives the best match)
            cv::TM_SQDIFF_NORMED = 1, (minimum value gives the best match)
            cv::TM_CCORR = 2,
            cv::TM_CCORR_NORMED = 3,
            cv::TM_CCOEFF = 4,
            cv::TM_CCOEFF_NORMED = 5
    """


    def __init__(
        self,
        max_matching: float, # matches above this threshold are considered as valid matches and further matching is stopped
        upper_bound: float, # matches above this threshold are considered as valid matches but further matching proceeds
        lower_bound: float, # matches below this threshold are considered as invalid matches
        scale_upper_bound: float, # upper bound of the scale factors
        scale_lower_bound: float, # lower bound of the scale factors
        scale_method: str, # scaling method can be either "scale_template" or "scale_screenshot"
        scale_space: int, # scaling space can be either "geomspace" or "linspace"
        scale_order: str, # scale order can be either "ascending" (small to large) or "descending" (large to small)
        match_intensity: int, # scaling steps between scale's upper and lower bound
        match_algorithm: int # opencv matching algorithm (integer value)
    ):
        self.max_matching = max_matching
        self.upper_bound = upper_bound
        self.lower_bound = lower_bound
        self.scale_upper_bound = scale_upper_bound
        self.scale_lower_bound = scale_lower_bound
        self.scale_method = scale_method
        self.scale_space = scale_space
        self.scale_order = scale_order
        self.match_intensity = match_intensity
        self.match_algorithm = match_algorithm


    def locate(self, screenshot: bytes, patterns: List[dict]) -> List[dict]:
        logger.info(f"Locating pattern matches with pattern locator for {len(patterns)} patterns")

        if self.scale_method == "scale_screenshot":
            return self.match_pattern_scale_screenshot(screenshot, patterns)
        elif self.scale_method == "scale_template":
            return self.match_pattern_scale_template(screenshot, patterns)
        else:
            raise Exception(f"Unknown scaling method: {self.scale_method}")


    def match_pattern_scale_template(self, input_image: bytes, template_images: List[dict]) -> List[dict]:
        """
        Find the best pattern matchings of the template images on the input image.
        This algorithm scales the template images and matches them on the input image.
        """
        # convert input image into NDArray[float64]
        input_image_array = numpy.frombuffer(input_image, numpy.uint8)
        # convert input image into cv2 format
        input_image_cv2 = cv2.imdecode(input_image_array, cv2.IMREAD_COLOR)
        # convert input image to grayscale
        input_image_gray = cv2.cvtColor(input_image_cv2, cv2.COLOR_BGR2GRAY)

        # do not scale input image
        input_image_scale = 1
        input_image_scaled = imutils.resize(
            input_image_gray,
            width=int(input_image_gray.shape[1] * input_image_scale)
        )
        (ih, iw) = input_image_scaled.shape[:2]

        # store all pattern matches
        pattern_matches = []

        # loop over template images
        for template_image in template_images:
            logger.info(f"Pattern matching template image filename: {template_image['filename']}")

            # scale space: linspace or geomspace
            if self.scale_space == "linspace":
                scales = numpy.linspace(self.scale_lower_bound, self.scale_upper_bound, self.match_intensity)
            elif self.scale_space == "geomspace":
                scales = numpy.geomspace(self.scale_lower_bound, self.scale_upper_bound, self.match_intensity)
            else:
                raise Exception(f"Unknown scale space: {self.scale_space}")

            # scale order: ascending or descending
            if self.scale_order == "ascending":
                scales = scales
            elif self.scale_order == "descending":
                scales = scales[::-1]
            else:
                raise Exception(f"Unknown scale order: {self.scale_order}")

            # loop over scale factors
            for template_image_scale in scales:
                logger.info(f"Pattern matching template image scale: {template_image_scale}")

                # scale template image
                template_image_scaled = imutils.resize(
                    template_image["grayscale"],
                    width=int(template_image["grayscale"].shape[1] * template_image_scale)
                )
                (th, tw) = template_image_scaled.shape[:2]

                # if input image is smaller than template image, skip pattern matching
                if ih < th or iw < tw:
                    logger.info(f"Input image ({iw}x{ih}) is smaller than template image ({tw}x{th})")
                    continue

                # run pattern matching algorithm
                result = cv2.matchTemplate(input_image_scaled, template_image_scaled, self.match_algorithm)
                (min_val, max_val, min_loc, max_loc) = cv2.minMaxLoc(result)
                if self.match_algorithm in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                    min_val, max_val = 1 - max_val, 1 - min_val
                    min_loc, max_loc = max_loc, min_loc
                logger.info(f"Pattern matching result: max_val={max_val} max_loc={max_loc}")

                # if pattern matching result is below lower bound, discard it
                if max_val < self.lower_bound:
                    logger.info(f"Pattern matching result ({max_val}) is below lower bound ({self.lower_bound})")
                    continue

                # store pattern matching result
                pattern_matches.append({
                    "tf": template_image["filename"],
                    "isc": input_image_scale,
                    "tsc": template_image_scale,
                    "min_val": min_val,
                    "max_val": max_val,
                    "min_loc": min_loc,
                    "max_loc": max_loc,
                    "th": th,
                    "tw": tw,
                    "ih": ih,
                    "iw": iw
                })

                # if pattern matching result exceeds max matching, skip further pattern matching
                if max_val > self.max_matching:
                    logger.info(f"Pattern matching result ({max_val}) is above max matching ({self.max_matching})")

                    # sort pattern matches by max_val (accuracy of pattern match)
                    pattern_matches = sorted(pattern_matches, key=lambda x: x["max_val"], reverse=True)

                    return pattern_matches

        # sort pattern matches by max_val (accuracy of pattern match)
        pattern_matches = sorted(pattern_matches, key=lambda x: x["max_val"], reverse=True)

        return pattern_matches


    def match_pattern_scale_screenshot(self, input_image: bytes, template_images: List[dict]) -> List[dict]:
        """
        Find the best pattern matchings of the template images on the input image.
        This algorithm scales the input image and matches the template images on the input image.
        """
        # convert input image into NDArray[float64]
        input_image_array = numpy.frombuffer(input_image, numpy.uint8)
        # convert input image into cv2 format
        input_image_cv2 = cv2.imdecode(input_image_array, cv2.IMREAD_COLOR)
        # convert input image to grayscale
        input_image_gray = cv2.cvtColor(input_image_cv2, cv2.COLOR_BGR2GRAY)

        # store all pattern matches
        pattern_matches = []

        # scale space: linspace or geomspace
        if self.scale_space == "linspace":
            scales = numpy.linspace(self.scale_lower_bound, self.scale_upper_bound, self.match_intensity)
        elif self.scale_space == "geomspace":
            scales = numpy.geomspace(self.scale_lower_bound, self.scale_upper_bound, self.match_intensity)
        else:
            raise Exception(f"Unknown scale space: {self.scale_space}")

        # scale order: ascending or descending
        if self.scale_order == "ascending":
            scales = scales
        elif self.scale_order == "descending":
            scales = scales[::-1]
        else:
            raise Exception(f"Unknown scale order: {self.scale_order}")

        # loop over scale factors
        for screenshot_image_scale in scales:
            logger.info(f"Pattern matching screenshot image scale: {screenshot_image_scale}")

            # scale input image
            input_image_scaled = imutils.resize(
                input_image_gray,
                width=int(input_image_gray.shape[1] * screenshot_image_scale)
            )
            (ih, iw) = input_image_scaled.shape[:2]

            # loop over template images
            for template_image in template_images:
                logger.info(f"Pattern matching template image filename: {template_image['filename']}")

                (th, tw) = template_image["grayscale"].shape[:2]

                # if input image is smaller than template image, skip pattern matching
                if ih < th or iw < tw:
                    logger.info(f"Input image ({iw}x{ih}) is smaller than template image ({tw}x{th})")
                    continue

                # run pattern matching algorithm
                result = cv2.matchTemplate(input_image_scaled, template_image["grayscale"], self.match_algorithm)
                (min_val, max_val, min_loc, max_loc) = cv2.minMaxLoc(result)
                if self.match_algorithm in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                    min_val, max_val = 1 - max_val, 1 - min_val
                    min_loc, max_loc = max_loc, min_loc
                logger.info(f"Pattern matching result: max_val={max_val} max_loc={max_loc}")

                # if pattern matching result is below lower bound, discard it
                if max_val < self.lower_bound:
                    logger.info(f"Pattern matching result ({max_val}) is below lower bound ({self.lower_bound})")
                    continue

                # store pattern matching result
                pattern_matches.append({
                    "tf": template_image["filename"],
                    "isc": screenshot_image_scale,
                    "tsc": 1,
                    "min_val": min_val,
                    "max_val": max_val,
                    "min_loc": min_loc,
                    "max_loc": max_loc,
                    "th": th,
                    "tw": tw,
                    "ih": ih,
                    "iw": iw
                })

                # if pattern matching result exceeds max matching, skip further pattern matching
                if max_val > self.max_matching:
                    logger.info(f"Pattern matching result ({pattern_matches['max_val']}) is above max matching ({self.max_matching})")

                    # sort pattern matches by max_val (accuracy of pattern match)
                    pattern_matches = sorted(pattern_matches, key=lambda x: x["max_val"], reverse=True)

                    return pattern_matches

        # sort pattern matches by max_val (accuracy of pattern match)
        pattern_matches = sorted(pattern_matches, key=lambda x: x["max_val"], reverse=True)

        return pattern_matches
