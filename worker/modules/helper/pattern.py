import logging
import cv2
import numpy
from pathlib import Path
from typing import List
from config.idp_rules import IdpRules


logger = logging.getLogger(__name__)


class PatternHelper:


    PATTERNS_BASE_DIR = Path(__file__).parent.parent.parent / "config" / "idp_patterns"


    @staticmethod
    def get_patterns_of_idp(size: str, idp: str) -> dict:
        return PatternHelper.get_patterns_in_directory(
            PatternHelper.PATTERNS_BASE_DIR / size / IdpRules[idp]["logos"]
        )


    @staticmethod
    def get_patterns_in_directory(path: Path) -> List[dict]:
        patterns = [] # [{"filename": "foo.png", "grayscale": <numpy.ndarray>}, ...]
        files = [f for f in path.iterdir() if f.suffix in [".jpg", ".png"]]
        for file in files:
            patterns.append({
                "filename": file.name,
                "grayscale": PatternHelper.get_grayscale_from_image(file)
            })
        return patterns


    @staticmethod
    def get_grayscale_from_image(path: Path) -> numpy.ndarray:
        image = cv2.imread(f"{path.resolve()}")
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return grayscale
