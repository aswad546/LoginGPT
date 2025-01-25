import logging
import subprocess


logger = logging.getLogger(__name__)


class Crawling:


    def __init__(self, config: dict, result: dict):
        self.resolved_url = result["resolved"]["url"]
        pass


    def start(self):
        script_path = 'crawler.js'
        args = [
            "node",
            script_path,
            self.resolved_url,
        ]

        logger.info(f"Starting crawling login page detection for url: {self.resolved_url}")

        # Run the subprocess
        try:
            result = subprocess.run(
                args,  # Command and arguments
                capture_output=True,  # Capture stdout and stderr
                text=True,            # Decode output as text
                check=True            # Raise an error if the command fails
            )
            logger.info("Puppeteer script executed successfully")
            logger.debug(f"Script output: {result.stdout}")


        except subprocess.CalledProcessError as e:
            logger.error("Error executing Puppeteer script")
            logger.error(f"stderr: {e.stderr}")
            raise Exception("Get focked")