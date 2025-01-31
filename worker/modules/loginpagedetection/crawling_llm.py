import logging
import subprocess
import socket
import time
import json
import os
import re

logger = logging.getLogger(__name__)

class Crawling:
    def __init__(self, config: dict, result: dict, domain):
        self.resolved_url = result["resolved"]["url"]
        self.domain = domain
        pass

    def classify_screenshots(self):
        """Send the resolved URL to the host socket server on port 5050."""
        HOST = "172.17.0.1"  # Allows connection to host from inside Docker (default host address for Docker)
        PORT = 5050

        logger.info(f"Sending URL '{self.domain}' to socket server at {HOST}:{PORT}")

        # Create a socket and connect
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            try:
                client_socket.connect((HOST, PORT))
                client_socket.sendall(self.domain.encode("utf-8"))
                
                # Receive confirmation from server
                response = client_socket.recv(1024).decode("utf-8")
                logger.info(f"Received from server: {response}")
            
            except (ConnectionRefusedError, socket.gaierror) as e:
                logger.error(f"Socket connection failed: {e}")
                raise Exception("Error: Could not connect to socket server")
            
    # Screenshots are labelled page_1.png, page_4.png etc 
    # TODO: Replace with regex
    def extract_page_number(self, file_name):
        collect = ''
        for char in file_name:
            if char >= '0' and char <= '9':
                collect += char
        return int(collect)


    def read_action_file(self, actions_file_path):
        click_sequence = []
        with open(actions_file_path, 'r') as act:
            actions = json.load(act)
            for action in actions:
                if action['clickPosition'] is not None:
                    click_sequence.append((action['clickPosition']['x'], action['clickPosition']['y']))
        return actions, click_sequence


    def find_minimum_path_to_login_urls_for_flow(self, files, actions, login_pages, click_sequence):
        for file in files:
            try:
                # Add regex here
                page_number = self.extract_page_number(file)
                relevant_action = actions[page_number - 1]
                action_url = relevant_action['url']
                relevant_click_sequence = click_sequence[:page_number - 1]
                # One login url may only have one login page (across all flows), find shortest path (number of clicks) to reach this page
                if action_url not in login_pages or len(login_pages[action_url]) > len(relevant_click_sequence):
                    login_pages[action_url] = actions[:page_number - 1]
            except Exception as e:
                print(f'Finding actions for the following file {dir}/{file} failed due to {e}')
                logger.error(f'Failed to find minimum path to login for {action_url}')


    def process_actions(self, output_dir, raw_results_dir):
        login_pages = {}
        for dir, _, files in os.walk(output_dir):
            if 'flow_' in dir:
                _, _, url, flow = dir.split('/')
                # Preprocess and collect all clicks upto a potential login page for each flow
                actions_file_path = os.path.join(raw_results_dir, flow,  f'click_actions_{flow}.json')
                actions, click_sequence = self.read_action_file(actions_file_path)
                self.find_minimum_path_to_login_urls_for_flow(files, actions, login_pages, click_sequence)
        return login_pages



    def start(self):
        script_path = '/app/modules/loginpagedetection/crawler.js'
        args = [
            "node",
            script_path,
            self.domain,
        ]

        logger.info(f"Starting crawling login page detection for url: {self.domain}")

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
            logger.info("Classifying pages (begin)")
            self.classify_screenshots()
            logger.info("Classifying pages (end)")
            # Find minimal set of actions and unique URLs from Crawl

            logger.info('Finding valid urls')
            output_dir = f'/app/modules/loginpagedetection/output_images/{self.domain.replace('.', '_')}'
            raw_results_dir = f'/app/modules/loginpagedetection/screenshot_flows/{self.domain.replace('.', '_')}'
            login_pages = self.process_actions(output_dir, raw_results_dir)

            for url, actions in login_pages.items():
                self.result["login_page_candidates"].append({
                    'login_page_candidate': url,
                    'login_page_strategy': 'CRAWLING',
                    'login_page_actions': actions
            })
            logger.info(f'Completed crawling url: {self.domain}')
        except subprocess.CalledProcessError as e:
            logger.error("Error executing Puppeteer script")
            logger.error(f"stderr: {e.stderr}")
            raise Exception("")
        except Exception as e:
            logger.warning(f'Error while crawling: {self.domain}')
            logger.debug(e)