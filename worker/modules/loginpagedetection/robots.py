import logging
from typing import List, Tuple
from requests.exceptions import RequestException
from urllib.parse import urlparse, unquote
from modules.browser.browser import RequestsBrowser
from modules.helper.url import URLHelper


logger = logging.getLogger(__name__)


class Robots:


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result

        self.login_page_url_regexes = config["login_page_config"]["login_page_url_regexes"]
        self.max_candidates = config["login_page_config"]["robots_strategy_config"]["max_candidates"]
        self.timeout_fetch_robots = config["login_page_config"]["robots_strategy_config"]["timeout_fetch_robots"]
        self.store_robots = config["artifacts_config"]["store_robots"]

        self.resolved_url = result["resolved"]["url"]


    def start(self):
        logger.info(f"Starting robots login page detection for: {self.resolved_url}")

        try:
            parsed_url = urlparse(self.resolved_url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

            logger.info(f"Requesting robots.txt on: {robots_url}")
            s = RequestsBrowser.chrome_session()
            r = s.get(robots_url, timeout=self.timeout_fetch_robots)

            # https://datatracker.ietf.org/doc/html/rfc9309#name-access-method
            # MUST be accessible in "/robots.txt"
            # MUST be "text/plain"
            if r.status_code == 200 and "text/plain" in r.headers.get("Content-Type", ""):
                logger.info(f"Found robots.txt on: {robots_url}")
                robots_txt = r.text

                if self.store_robots:
                    self.result["robots"] = robots_txt

                # get all robots paths
                robots_candidates = self.paths_from_robots_txt(robots_txt)

                # filter and prioritize robots paths
                robots = []
                for (stm, path) in robots_candidates:

                    # only consider paths with regex matches (prio > 0)
                    priority = URLHelper.prio_of_url(path, self.login_page_url_regexes)
                    if priority["priority"] > 0:

                        # avoid duplicate robots paths
                        lpc = f"{parsed_url.scheme}://{parsed_url.netloc}{path}"
                        if lpc not in [r["login_page_candidate"] for r in robots]:

                            # store robots path as login page candidate
                            robots.append({
                                "login_page_candidate": URLHelper.normalize(lpc),
                                "login_page_strategy": "ROBOTS",
                                "login_page_priority": priority,
                                "login_page_info": {
                                    "path": path,
                                    "stm": stm
                                }
                            })

                # sort robots paths by priority
                robots = sorted(robots, key=lambda r: r["login_page_priority"]["priority"], reverse=True)

                # store robots paths in result
                for i, e in enumerate(robots):
                    if i < self.max_candidates: self.result["login_page_candidates"].append(e)
                    # else: self.result["additional_login_page_candidates"].append(e)

            else:
                logger.info(f"Did not find robots.txt on: {robots_url}")

        except RequestException as e:
            logger.info(f"Error while requesting robots.txt on: {robots_url}")
            logger.debug(e)


    @staticmethod
    def paths_from_robots_txt(robots_txt: str) -> List[Tuple[str, str]]:
        # parse robots.txt file and return list of ("allow"|"disallow", "path") tuples
        # source: https://github.com/python/cpython/blob/3.11/Lib/urllib/robotparser.py#L81
        robots_paths = []
        for line in robots_txt.split("\n"):
            i = line.find("#")
            if i >= 0:
                line = line[:i]
            line = line.strip()
            if not line: continue
            line = line.split(":", 1)
            if len(line) == 2:
                line[0] = line[0].strip().lower()
                line[1] = unquote(line[1].strip())
                if line[0] == "user-agent":
                    pass
                elif line[0] == "disallow":
                    if line[1].startswith("/"):
                        robots_paths.append((line[0], line[1]))
                elif line[0] == "allow":
                    if line[1].startswith("/"):
                        robots_paths.append((line[0], line[1]))
                elif line[0] == "crawl-delay":
                    pass
                elif line[0] == "request-rate":
                    pass
                elif line[0] == "sitemap":
                    pass
        return robots_paths
