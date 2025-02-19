import json
import os
from pprint import pprint
def extract_page_number( file_name):
    collect = ''
    for char in file_name:
        if char >= '0' and char <= '9':
            collect += char
    return int(collect)


def read_action_file( actions_file_path):
    click_sequence = []
    with open(actions_file_path, 'r') as act:
        actions = json.load(act)
        for action in actions:
            if action['clickPosition'] is not None:
                click_sequence.append((action['clickPosition']['x'], action['clickPosition']['y']))
    return actions, click_sequence


def find_minimum_path_to_login_urls_for_flow( files, actions, login_pages, click_sequence):
    for file in files:
        try:
            # Add regex here
            print(file)
            page_number = extract_page_number(file)
            print(page_number)
            print(len(actions), page_number-1)
            offset = page_number - 1 if page_number - 1 != len(actions) else 2
            relevant_action = actions[offset]
            print('here1')
            action_url = relevant_action['url']
            relevant_click_sequence = click_sequence[:offset]
            # One login url may only have one login page (across all flows), find shortest path (number of clicks) to reach this page
            if action_url not in login_pages or len(login_pages[action_url]) > len(relevant_click_sequence):
                login_pages[action_url] = actions[:offset]
        except Exception as e:
            print(f'Finding actions for the following file {dir}/{file} failed due to {e}')


def process_actions(output_dir, raw_results_dir):
    login_pages = {}
    for dir, _, files in os.walk(output_dir):
        if 'flow_' in dir:
            url, flow = dir.split('/')[-2:]
            print(url, flow)
            # Preprocess and collect all clicks upto a potential login page for each flow
            actions_file_path = os.path.join(raw_results_dir, flow,  f'click_actions_{flow}.json')
            actions, click_sequence = read_action_file(actions_file_path)
            find_minimum_path_to_login_urls_for_flow(files, actions, login_pages, click_sequence)
    return login_pages

if __name__ == '__main__':
    output = '/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/output_images/www_illimitybank_com'
    input = '/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/screenshot_flows/www_illimitybank_com'
    login_pages = process_actions(output, input)