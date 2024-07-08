import logging
from typing import Tuple, List
from playwright.sync_api import Error, TimeoutError, Page, Request
from modules.browser.browser import PlaywrightHelper
from modules.helper.url import URLHelper


logger = logging.getLogger(__name__)


class DetectionHelper:


    @staticmethod
    def get_lpcs_with_idxs(login_page_candidates: List[dict]) -> List[Tuple[str, List[int]]]:
        """ Returns list of tuples containing a unique login page candidate url and a list of indices.
            Input: [
                {"login_page_candidate": "https://foo.com/login"},
                {"login_page_candidate": "https://foo.com/signin"},
                {"login_page_candidate": "https://foo.com/login"}
            ]
            Output: [
                ("https://foo.com/login", [0, 2]),
                ("https://foo.com/signin", [1])
            ]
        """
        lpcs_with_idxs = []
        unique_lpc_urls = set([lpc["login_page_candidate"] for lpc in login_page_candidates])
        for lpc_url in unique_lpc_urls:
            lpc_idxs = [i for i, lpc in enumerate(login_page_candidates) if lpc["login_page_candidate"] == lpc_url]
            lpcs_with_idxs.append((lpc_url, lpc_idxs))
        return lpcs_with_idxs


    @staticmethod
    def get_lpcs_with_idps(
        lpcs_with_idps: dict,
        login_page_candidates: List[dict],
        recognized_idps: List[dict],
        recognition_mode: str,
        idp_scope: List[str],
        is_update: bool
    ):
        """ Updates the login page candidates and the idps to scan based on the recognition mode.
            lpcs_with_idps: {"https://foo.com/bar": ["APPLE", "GOOGLE", ...], ...}
            Param is_update is set to false when this function is called at the beginning of each recognition run.
            Param is_update is set to true when this function is called at the beginning of each login page scan.
            The recognized idps can change during the recognition run of a login page, which may affect
            the idps that need to be scanned on the remaining login page.
        """

        # fill login pages with all idps
        if not lpcs_with_idps:
            for lpc in login_page_candidates:
                lpcs_with_idps[lpc["login_page_candidate"]] = idp_scope.copy()

        # remove already detected idps from login pages
        for ridp in recognized_idps:

            if recognition_mode == "FAST":

                for lp in lpcs_with_idps:
                    if ridp["login_page_url"] != lp:
                        # remove all idps from all login pages that are not fast login page
                        lpcs_with_idps[lp] = []
                    else:
                        # remove found idp from fast login page
                        if ridp["idp_name"] in lpcs_with_idps[lp]:
                            lpcs_with_idps[lp].remove(ridp["idp_name"])

            elif recognition_mode == "NORMAL":

                # remove already found idp from *all* login pages
                for lp in lpcs_with_idps:
                    if ridp["idp_name"] in lpcs_with_idps[lp]:
                        lpcs_with_idps[lp].remove(ridp["idp_name"])

            elif recognition_mode == "EXTENSIVE":

                # remove already found idp from *its* login page
                if ridp["idp_name"] in lpcs_with_idps[ridp["login_page_url"]]:
                    lpcs_with_idps[ridp["login_page_url"]].remove(ridp["idp_name"])

        # in normal mode, and if idps were recognized, remove all login pages on which no idps were found
        if recognition_mode == "NORMAL" and recognized_idps and not is_update:
            for lp in lpcs_with_idps:
                if lp not in [ridp["login_page_url"] for ridp in recognized_idps]:
                    lpcs_with_idps[lp] = []


    @staticmethod
    def get_lpc_from_url(url: str, login_page_candidates: List[dict]) -> dict:
        for lpc in login_page_candidates:
            if lpc["login_page_candidate"] == url:
                return lpc
        return {}


    @staticmethod
    def get_coordinate_metadata(page: Page, x: float, y: float) -> Tuple[List[str], List[str]]:
        tags = f"""
            () => {{
                let tree = document.elementsFromPoint({x},{y});
                let out = [];
                tree.forEach((e, i) => {{out.push(e.tagName);}});
                return out;
            }}
        """
        outerhtml = f"""
            () => {{
                let out = [];
                let tree = document.elementsFromPoint({x},{y});
                for (let e of tree) {{
                    if (e.tagName === "BODY") break;
                    out.push(e.outerHTML);
                }}
                return out;
            }}
        """
        try:
            logger.info(f"Determine metadata for coordinate ({x}, {y}) on: {page.url}")
            tags_list = page.evaluate(tags)
            outerhtml_list = page.evaluate(outerhtml)
            if type(tags_list) != list:
                logger.warning(f"Tags list is of type {type(tags_list)}, using empty list")
                tags_list = []
            if type(outerhtml_list) != list:
                logger.info(f"Outerhtml list is of type {type(outerhtml_list)}, using empty list")
                outerhtml_list = []
            logger.info(f"Tags list contains {len(tags_list)} items")
            logger.info(f"Outerhtml list contains {len(outerhtml_list)} items")
            return tags_list, outerhtml_list
        except Error as e:
            logger.warning(f"Error while determining metadata for coordinate ({x}, {y}) on: {page.url}")
            logger.debug(e)
            return [], []


    @staticmethod
    def click_coordinate_check_url(
        page: Page, browser_config: dict, coordinate: Tuple[float, float],
        domain_regex: str, path_regex: str, params_regex: List[dict]
    ) -> Tuple[bool, str, bool, bool, str]:
        logger.info(f"Click on coordinate ({coordinate[0]}, {coordinate[1]}) and match requests on regex")
        logger.info(f"Domain: {domain_regex}, Path: {path_regex}, Params: {params_regex}")

        # store details of the first request match
        match_url = None # str, url of the matched request
        match_frame = None # Frame, frame of the matched request
        match_popup = None # bool, whether a popup was opened
        match_iframe = None # bool, whether the matched request was in an iframe
        match_screenshot = None # str, base64 compressed screenshot of the matched request frame

        # intercepts all requests
        def interceptor(request: Request):
            nonlocal match_url, match_frame
            logger.debug(f"Intercepted request url: {request.url}")
            if (
                match_url is None # only store the first request match
                and request.is_navigation_request() # only match top level navigation requests
                and URLHelper.match_url(request.url, domain_regex, path_regex, params_regex) # match request url on regex
            ):
                logger.info(f"Matched request url: {request.url}")
                match_url = request.url
                match_frame = request.frame

        # activate request interception
        page.context.on("request", interceptor)

        # click on coordinate
        try:
            with page.expect_popup(timeout=2_000) as page_info:
                logger.info(f"Click on coordinate ({coordinate[0]}, {coordinate[1]}) and wait for popup")
                page.mouse.click(coordinate[0], coordinate[1])
            logger.info("Popup opened after clicking coordinate, waiting for popup to load")
            match_popup = True
            PlaywrightHelper.wait_for_page_load(page_info.value, browser_config)
        except TimeoutError:
            logger.info("No popup opened after clicking coordinate, waiting for page to load")
            match_popup = False
            PlaywrightHelper.wait_for_page_load(page, browser_config)
        except Error:
            logger.info("Popup immediately closed after opening, waiting for page to load")
            match_popup = True
            PlaywrightHelper.wait_for_page_load(page, browser_config)

        # deactivate request interception
        page.context.remove_listener("request", interceptor)

        # screenshot of matched request frame
        if match_url:
            try:
                logger.info("Wait for match frame to take screenshot")
                PlaywrightHelper.wait_for_page_load(match_frame, browser_config)
                match_screenshot = PlaywrightHelper.take_screenshot(match_frame.page)
            except Error as e:
                logger.warning("Error while taking screenshot of match frame page")
                logger.debug(e)
            except Exception as e:
                logger.warning("Exception while taking screenshot of match frame page")
                logger.debug(e)

        # return request match
        return (True if match_url else False, match_url, match_popup, match_iframe, match_screenshot)
