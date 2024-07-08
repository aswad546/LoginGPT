import re
import json
import tldextract
from urllib import parse
from typing import List
from url_normalize import url_normalize
from datetime import datetime
from playwright.sync_api import Request


class URLHelper:


    @staticmethod
    def get_tld(url: str) -> str:
        return tldextract.extract(url).registered_domain


    @staticmethod
    def is_same_tld(url1: str, url2: str) -> bool:
        return tldextract.extract(url1).registered_domain == tldextract.extract(url2).registered_domain


    @staticmethod
    def normalize(url: str) -> str:
        return url_normalize(url)


    @staticmethod
    def prio_of_url(url: str, url_regexes: List[dict]) -> dict:
        """ Returns highest priority of url based on match with url regexes """
        prio = {"regex": None, "priority": 0}
        for r in url_regexes:
            if re.compile(r["regex"], re.IGNORECASE).search(url):
                if r["priority"] > prio["priority"]:
                    prio = {"regex": r["regex"], "priority": r["priority"]}
        return prio


    @staticmethod
    def parse_inbc(request: Request, inbc_type: str) -> dict:
        """ Parses in-browser communication from playwright request and returns in-browser message or None """
        if inbc_type == "POSTMESSAGE" and request.url != "https://mock.sso-monitor.me/postmessage": return None
        elif inbc_type == "CHANNELMESSAGE" and request.url != "https://mock.sso-monitor.me/channelmessage": return None
        if request.method != "POST": return None
        if type(request.post_data_json) is not dict: return None

        date = request.post_data_json.get("date")
        origin = request.post_data_json.get("origin")
        location = request.post_data_json.get("documentLocation")
        title = request.post_data_json.get("documentTitle")
        data = request.post_data_json.get("data")

        msg = {
            "timestamp": None,
            "initiator_origin": None,
            "receiver_url": None,
            "receiver_origin": None,
            "receiver_title": None,
            "data": None
        }
        if date: msg["timestamp"] = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
        if origin: msg["initiator_origin"] = origin
        if location: msg["receiver_url"] = location.get("href")
        if location: msg["receiver_origin"] = location.get("origin")
        if title: msg["receiver_title"] = title
        if type(data) is str:
            try: msg["data"] = json.loads(data) # try to parse strings containing json
            except json.decoder.JSONDecodeError: msg["data"] = data # fallback to string
        else: msg["data"] = data

        return msg


    @staticmethod
    def match_url(url: str, domain_regex: str, path_regex: str, parameters_regex: List[dict]) -> bool:
        """ Checks if the given url matches the given regexes for domain, path, and parameters.
            domain_regex: regex for the domain
            path_regex: regex for the path
            parameters_regex: list of dicts with keys "name" and "value" for the parameter name and value regexes
        """
        parsed_url = parse.urlsplit(url)
        matched_domain = re.search(domain_regex, parsed_url.netloc)
        matched_path = re.search(path_regex, parsed_url.path)
        matched_query_params = URLHelper.match_params(parameters_regex, parse.parse_qs(parsed_url.query))
        matched_fragment_params = URLHelper.match_params(parameters_regex, parse.parse_qs(parsed_url.fragment))
        return matched_domain and matched_path and (matched_query_params or matched_fragment_params)


    @staticmethod
    def match_post_data(url: str, post_data: dict, domain_regex: str, path_regex: str, parameters_regex: List[dict]) -> bool:
        """ Checks if the given url and post data matches the given regexes for domain, path, and parameters.
            domain_regex: regex for the domain
            path_regex: regex for the path
            parameters_regex: list of dicts with keys "name" and "value" for the parameter name and value regexes
        """
        parsed_url = parse.urlsplit(url)
        matched_domain = re.search(domain_regex, parsed_url.netloc)
        matched_path = re.search(path_regex, parsed_url.path)
        matched_post_data_params = URLHelper.match_params(parameters_regex, post_data)
        return matched_domain and matched_path and matched_post_data_params


    @staticmethod
    def match_inbc_data(pm_data: dict, domain_regex: str, path_regex: str, parameters_regex: List[dict]) -> bool:
        """ Recursively checks if the given postmessage matches the given regexes for domain, path, and parameters.
            domain_regex: regex for the domain
            path_regex: regex for the path
            parameters_regex: list of dicts with keys "name" and "value" for the parameter name and value regexes
        """
        def match_traverse(pm_data: dict, domain_regex: str, path_regex: str, parameter_regex: dict) -> bool:
            if type(pm_data) is not dict: return False
            for k, v in pm_data.items():
                if type(v) is str:
                    if re.match(parameter_regex["name"], k) and re.match(parameter_regex["value"], v):
                        return True
                elif type(v) is dict:
                    return match_traverse(v, domain_regex, path_regex, parameter_regex)
        for param_regex in parameters_regex:
            match = match_traverse(pm_data, domain_regex, path_regex, param_regex)
            if not match: return False
        return True # all parameters matched


    @staticmethod
    def match_params(parameters_regex: List[dict], parameters: dict) -> bool:
        """ Checks if the given parameters match the given regexes.
            parameters_regex: list of dicts with keys "name" and "value" for the parameter name and value regexes
            parameters: dict of parameters with parameter names as keys and lists of parameter values as values
        """
        for param_regex in parameters_regex:
            match = False
            for param in parameters:
                if re.match(param_regex["name"], param): # if parameter name matches
                    if type(parameters[param]) is list:
                        for param_value in parameters[param]: # check if any of parameter values matches
                            if re.match(param_regex["value"], param_value): # one of parameter values matches
                                match = True # parameter matches
                    elif type(parameters[param]) is str: # check if parameter value matches
                        if re.match(param_regex["value"], parameters[param]): # parameter value matches
                            match = True # parameter matches
            if not match: return False # none of parameter names or values matched regex
        return True # all parameters matched
