import re

def extract_domain(url):
    match = re.match(r'^(https?://[^/]+)', url)
    return match.group(1) if match else None
    