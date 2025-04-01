from crawling_llm import Crawling

if __name__ == "__main__":
    import pprint
    print('Running')

    domain = "www.marion_bank.com"  # change this to your actual domain
    adjustedURL = domain.replace('.', '_')

    output_dir = f'/u1/a8tariq/SSO-Monitor/worker/modules/loginpagedetection/output_images/{adjustedURL}'
    raw_results_dir = f'/u1/a8tariq/SSO-Monitor/worker/modules/loginpagedetection/screenshot_flows/{adjustedURL}'

    dummy_result = {
        "resolved": {
            "url": f"https://{domain}"
        },
        "login_page_candidates": []
    }

    config = {}
    print(output_dir)
    print(raw_results_dir)

    crawler = Crawling(config=config, result=dummy_result, domain=domain)

    login_pages = crawler.process_actions(output_dir, raw_results_dir)

    pprint.pprint(login_pages)
