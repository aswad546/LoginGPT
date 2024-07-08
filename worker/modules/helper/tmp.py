import logging
import os
import uuid
import shutil
import contextlib


logger = logging.getLogger(__name__)


class TmpHelper:


    TMP_PATH = os.environ.get("TMP_PATH", "/tmpfs")


    @staticmethod
    @contextlib.contextmanager
    def tmp_file(ext: str = "") -> str:
        path = f"{TmpHelper.TMP_PATH}/{uuid.uuid4()}{f'.{ext}' if ext else ''}"
        logger.info(f"Creating tmp file: {path}")
        open(path, "w").close()
        yield path
        logger.info(f"Removing tmp file: {path}")
        os.remove(path)


    @staticmethod
    @contextlib.contextmanager
    def tmp_dir() -> str:
        path = f"{TmpHelper.TMP_PATH}/{uuid.uuid4()}/"
        logger.info(f"Creating tmp dir: {path}")
        os.makedirs(path, exist_ok=True)
        yield path
        logger.info(f"Removing tmp dir: {path}")
        shutil.rmtree(path)
