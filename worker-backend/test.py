import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_directory_creation(path):
    try:
        os.makedirs(path, exist_ok=True)
        logger.info(f"Successfully created directory: {path}")
    except Exception as e:
        logger.error(f"Failed to create directory at {path}: {e}")

if __name__ == "__main__":
    # Change this path as needed for your environment.
    test_path = "/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/output_images/test_dir"
    test_directory_creation(test_path)
