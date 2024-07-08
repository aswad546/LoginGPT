import json
import argparse
from playwright.sync_api import sync_playwright


IDPS = {
    "GOOGLE": {
        "login_url": "https://accounts.google.com",
        "cookie_urls": [
            "https://accounts.google.com"
        ]
    }
}


def main():
    parser = argparse.ArgumentParser(description="Generate idp cookie store")
    parser.add_argument("idp", type=str, choices=IDPS.keys(), help="idp name")
    args = parser.parse_args()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context()
        page = context.new_page()

        page.goto(IDPS[args.idp]["login_url"])
        _ = input("Submit idp credentials and press enter to continue")
        cookies = context.cookies(urls=IDPS[args.idp]["cookie_urls"])
        print(json.dumps(cookies))

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
