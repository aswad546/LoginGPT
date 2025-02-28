import logging
from modules.helper.url import URLHelper
from lib.usp.tree import sitemap_tree_for_homepage
from lib.usp.web_client.requests_client import RequestsWebClient
from lib.usp.exceptions import SitemapException, \
    SitemapXMLParsingException, GunzipException, StripURLToHomepageException


logger = logging.getLogger(__name__)


class Sitemap:


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result

        self.login_page_url_regexes = config["login_page_config"]["login_page_url_regexes"]
        self.max_candidates = config["login_page_config"]["sitemap_strategy_config"]["max_candidates"]
        self.max_recursion_level = config["login_page_config"]["sitemap_strategy_config"]["max_recursion_level"]
        self.max_sitemap_size = config["login_page_config"]["sitemap_strategy_config"]["max_sitemap_size"]
        self.timeout_fetch_sitemap = config["login_page_config"]["sitemap_strategy_config"]["timeout_fetch_sitemap"]
        self.store_sitemap = config["artifacts_config"]["store_sitemap"]

        self.resolved_url = result["resolved"]["url"]


    def start(self):
        logger.info(f"Starting sitemap login page detection for: {self.resolved_url}")

        prio_sitemap = [] # list of sitemap urls w/out duplicates and prio > 0
        full_sitemap = [] # list of all sitemap urls
        try:
            # request sitemap urls
            client = RequestsWebClient()
            client.set_timeout(self.timeout_fetch_sitemap)
            try:
                tree = sitemap_tree_for_homepage(
                    self.resolved_url, web_client=client,
                    max_recursion_level=self.max_recursion_level,
                    max_sitemap_size=self.max_sitemap_size
                )
            except Exception as e: # catch all library bugs
                logger.warning(f"Error while requesting sitemap for: {self.resolved_url}")
                logger.debug(e)
                return

            # filter and prioritize sitemap urls
            for page in tree.all_pages():
                page_url = page.url
                page_priority = float(page.priority) if page.priority else None
                page_last_modified = page.last_modified.timestamp() if page.last_modified else None
                page_change_frequency = str(page.change_frequency) if page.change_frequency else None
                page_news_story = str(page.news_story) if page.news_story else None

                # store sitemap url in full sitemap
                full_sitemap.append({
                    "url": page_url,
                    "priority": page_priority,
                    "last_modified": page_last_modified,
                    "change_frequency": page_change_frequency,
                    "news_story": page_news_story
                })

                # only consider sitemap urls with regex matches (prio > 0)
                priority = URLHelper.prio_of_url(page_url, self.login_page_url_regexes)
                if priority["priority"] > 0:

                    # check if sitemap url is on same tld as resolved url
                    if not URLHelper.is_same_tld(self.resolved_url, page_url):
                        continue

                    # avoid duplicate sitemap urls
                    if page_url in [s["login_page_candidate"] for s in prio_sitemap]:
                        continue

                    # store sitemap url as login page candidate
                    prio_sitemap.append({
                        "login_page_candidate": URLHelper.normalize(page_url),
                        "login_page_strategy": "SITEMAP",
                        "login_page_priority": priority,
                        "login_page_info": {
                            "priority": page_priority,
                            "last_modified": page_last_modified,
                            "change_frequency": page_change_frequency,
                            "news_story": page_news_story
                        }
                    })

        except Exception as e:
            logger.warning(f"Error while requesting sitemap for: {self.resolved_url}")
            logger.debug(e)

        # sort sitemap urls by priority
        prio_sitemap = sorted(prio_sitemap, key=lambda k: k["login_page_priority"]["priority"], reverse=True)

        # store sitemap urls in result
        for i, s in enumerate(prio_sitemap):
            if i < self.max_candidates: self.result["login_page_candidates"].append(s)
            # else: self.result["additional_login_page_candidates"].append(s)

        # add full sitemap to result
        if self.store_sitemap and full_sitemap:
            self.result["sitemap"] = full_sitemap
