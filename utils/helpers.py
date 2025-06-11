import re

def extract_domain(url):
    match = re.match(r'^(https?://[^/]+)', url)
    return match.group(1) if match else None

# Returns items from a list that have a truthy value in a given dictionary
filter_by_dict_value = lambda d, arr: [k for k in arr if d.get(k)]