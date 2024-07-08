import logging
import json
from pathlib import Path
from typing import List, Any
from playwright.sync_api import Page


logger = logging.getLogger(__name__)


class NavigatorCredentialsDetector:


    JS_DIR = Path(__file__).parent.parent / "browser" / "js"


    def __init__(self, result: dict, page: Page):
        self.result = result
        self.page = page
        self.url = None

        self.page.add_init_script(path=f"{self.JS_DIR / 'navcred-tracker.js'}")
        self.page.expose_function("_ssomon_navcred_callback", self.callback)


    def register_callback(self, url: str):
        logger.info(f"Registering navigator credentials callback on: {url}")
        self.url = url


    def unregister_callback(self, url: str):
        logger.info(f"Unregistering navigator credentials callback from: {url}")
        self.url = None


    def callback(self, function_name: str, function_params: List[Any]):
        navcred = {
            "login_page_url": self.url,
            "function_name": function_name,
            "function_params": function_params
        }
        if self.url and not self.navcred_is_duplicate(navcred):
            self.result["recognized_navcreds"].append(navcred)


    def navcred_is_duplicate(self, navcred: dict) -> bool:
        for rnc in self.result["recognized_navcreds"]:
            if (
                rnc["login_page_url"] == navcred["login_page_url"] and
                rnc["function_name"] == navcred["function_name"] and
                json.dumps(rnc["function_params"]) == json.dumps(navcred["function_params"])
            ):
                return True
        return False
