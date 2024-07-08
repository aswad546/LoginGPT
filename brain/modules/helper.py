def find_sibling_data(data, target_key, target_value, sibling_key, results=None):
    if results is None:
        results = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key and value == target_value:
                sibling_value = data.get(sibling_key)
                if sibling_value is not None:
                    results.append(sibling_value)
            else:
                find_sibling_data(value, target_key, target_value, sibling_key=sibling_key, results=results)
    elif isinstance(data, list):
        for item in data:
            find_sibling_data(item, target_key, target_value, sibling_key=sibling_key, results=results)
    return results
