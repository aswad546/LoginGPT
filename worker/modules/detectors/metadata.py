import logging
import requests
from typing import Any
from urllib.parse import urlparse
from requests.exceptions import RequestException
from modules.browser.browser import RequestsBrowser


logger = logging.getLogger(__name__)


class MetadataDetector:


    def __init__(self, config: dict, result: dict):
        self.config = config
        self.result = result

        self.resolved_url = result["resolved"]["url"]
        self.parsed_url = urlparse(self.resolved_url)
        self.base_url = f"{self.parsed_url.scheme}://{self.parsed_url.netloc}"


    def start(self):
        logger.info(f"Starting metadata detection for domain: {self.base_url}")

        s = RequestsBrowser.chrome_session()

        self.result["metadata_data"] = {

            # https://datatracker.ietf.org/doc/html/rfc9309#name-access-method
            # MUST be accessible in a file named "/robots.txt"
            # MUST be Internet Media Type "text/plain"
            "robots_txt": self.request(s,
                f"{self.base_url}/robots.txt",
                statuscode=200,
                mime="text/plain",
                parsejson=False
            ),

            # https://datatracker.ietf.org/doc/html/rfc9116#name-location-of-the-securitytxt
            # MUST place the "security.txt" file under the "/.well-known/" path, e.g., https://example.com/.well-known/security.txt
            # MUST have a Content-Type of "text/plain" with the default charset parameter set to "utf-8"
            "security_txt": self.request(s,
                f"{self.base_url}/.well-known/security.txt",
                statuscode=200,
                mime="text/plain",
                parsejson=False
            ),

            # https://datatracker.ietf.org/doc/html/rfc7033#section-4
            # https://openid.net/specs/openid-connect-discovery-1_0.html#IssuerDiscovery
            # MUST be the well-known path "/.well-known/webfinger"
            # MUST return a JRD as the representation for the resource
            # media type used for the JSON Resource Descriptor (JRD) is "application/jrd+json"
            # MUST contain a "resource" parameter and MAY contain one or more "rel" parameters
            "webfinger": self.request(s,
                f"{self.base_url}/.well-known/webfinger?resource=acct%3Aalice%40gmail.com&rel=http%3A%2F%2Fopenid.net%2Fspecs%2Fconnect%2F1.0%2Fissuer",
                statuscode=200,
                mime="application/jrd+json",
                parsejson=True
            ),

            # https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderConfig
            # MUST make a JSON document available at the path formed by concatenating the string /.well-known/openid-configuration to the Issuer
            # MUST be returned using the application/json content type
            "openid_configuration": self.request(s,
                f"{self.base_url}/.well-known/openid-configuration",
                statuscode=200,
                mime="application/json",
                parsejson=True
            ),

            # https://datatracker.ietf.org/doc/html/rfc8414#section-3
            # URI string used is "/.well-known/oauth-authorization-server"
            # return a JSON object using the "application/json" content type
            "oauth_authorization_server": self.request(s,
                f"{self.base_url}/.well-known/oauth-authorization-server",
                statuscode=200,
                mime="application/json",
                parsejson=True
            ),

            # https://datatracker.ietf.org/doc/html/draft-looker-oauth-client-discovery-01#section-3
            # the well-known URI string used is "/.well-known/oauth-client"
            # MUST use the 200 OK HTTP status code and return a JSON object using the "application/json" content type
            "oauth_client": self.request(s,
                f"{self.base_url}/.well-known/oauth-client",
                statuscode=200,
                mime="application/json",
                parsejson=True
            ),

            # https://developer.chrome.com/docs/privacy-sandbox/fedcm/#well-known-file
            "web_identity": self.request(s,
                f"{self.base_url}/.well-known/web-identity",
                statuscode=200,
                mime="application/json",
                parsejson=True
            ),

            # https://mozilla.github.io/id-specs/docs/formats/well-known/
            # document must be located at /.well-known/browserid
            # must be served with Content-Type: application/json
            "browserid": self.request(s,
                f"{self.base_url}/.well-known/browserid",
                statuscode=200,
                mime="application/json",
                parsejson=True
            ),

            # https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets
            # JWKS endpoint for each tenant, which is found at https://{yourDomain}/.well-known/jwks.json
            "jwks": self.request(s,
                f"{self.base_url}/.well-known/jwks.json",
                statuscode=200,
                mime=None,
                parsejson=True
            ),

            # https://backstage.forgerock.com/docs/am/7/uma-guide/configure-uma-discovery.html
            "uma2_configuration": self.request(s,
                f"{self.base_url}/.well-known/uma2-configuration",
                statuscode=200,
                mime=None,
                parsejson=True
            ),

            # ???
            "fido_configuration": self.request(s,
                f"{self.base_url}/.well-known/fido-configuration",
                statuscode=200,
                mime=None,
                parsejson=True
            ),

            # ???
            "fido_2fa_configuration": self.request(s,
                f"{self.base_url}/.well-known/fido-2fa-configuration",
                statuscode=200,
                mime=None,
                parsejson=True
            ),

            # ???
            "fido2_configuration": self.request(s,
                f"{self.base_url}/.well-known/fido2-configuration",
                statuscode=200,
                mime=None,
                parsejson=True
            ),

            # https://developer.apple.com/documentation/xcode/supporting-associated-domains#Add-the-associated-domain-file-to-your-website
            # place it in your site's .well-known directory
            "apple_app_site_association": self.request(s,
                f"{self.base_url}/.well-known/apple-app-site-association",
                statuscode=200,
                mime=None,
                parsejson=True
            ),

            # https://developers.google.com/digital-asset-links/v1/create-statement
            # statement list is a text file located at the following address: scheme://domain/.well-known/assetlinks.json
            # must be served as Content-Type: application/json
            "assetlinks": self.request(s,
                f"{self.base_url}/.well-known/assetlinks.json",
                statuscode=200,
                mime="application/json",
                parsejson=True
            )

        }

        self.result["metadata_available"] = {}
        for k, v in self.result["metadata_data"].items():
            self.result["metadata_available"][k] = True if v else False


    @staticmethod
    def request(
        session: requests.Session,
        url: str,
        timeout: float = 10,
        statuscode: int = 200,
        mime: str = "application/json",
        parsejson: bool = True
    ) -> None|str|Any:
        try:
            logger.info(f"Metadata detection request: {url}")
            r = session.get(url, timeout=timeout)
            # check status code
            if statuscode and r.status_code != statuscode:
                logger.info(f"Invalid status code ({r.status_code} != {statuscode}) while requesting: {url}")
                return None
            # check mime type
            if mime and mime not in r.headers["Content-Type"]:
                logger.info(f"Invalid mime type ({r.headers['Content-Type']} != {mime}) while requesting: {url}")
                return None
            # parse json
            if parsejson: return r.json()
            else: return r.text
        except RequestException as e:
            logger.info(f"RequestException while requesting: {url}")
            logger.debug(e)
            return None
        except Exception as e:
            logger.info(f"Exception while requesting: {url}")
            logger.debug(e)
            return None
