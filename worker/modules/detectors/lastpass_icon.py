import logging
from playwright.sync_api import Frame
from modules.locators.lastpass_icon import LastpassIconLocator


logger = logging.getLogger(__name__)


class LastpassIconDetector:


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result


    def start(self, lpc_url: str, frame_idx: int, frame: Frame):
        logger.info(f"Starting lastpass icon detection in frame {frame_idx} on: {lpc_url}")

        elements = LastpassIconLocator.locate(frame)
        if elements:
            logger.info(f"Found lastpass icon in {len(elements)} elements")
            self.result["recognized_lastpass_icons"].append({
                "login_page_url": lpc_url,
                "recognition_strategy": "LASTPASS_ICON",
                "lastpass_icon_elements": elements,
                "lastpass_icon_frame": "IFRAME" if frame.parent_frame else "TOPMOST",
                "lastpass_icon_frame_index": frame_idx,
                "lastpass_icon_frame_url": frame.url,
                "lastpass_icon_frame_name": frame.name,
                "lastpass_icon_frame_title": frame.title(),
                "lastpass_icon_frames_length": len(frame.page.frames)
            })
