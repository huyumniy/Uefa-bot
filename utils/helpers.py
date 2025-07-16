import re
from datetime import datetime, time


def extract_domain(url):
    match = re.match(r'^(https?://[^/]+)', url)
    return match.group(1) if match else None

# Returns items from a list that have a truthy value in a given dictionary
filter_by_dict_value = lambda d, arr: [k for k in arr if d.get(k)]


def parse_time_string(time_str: str) -> time:
    """
    Convert a time string in the format 'HH:MM' to a datetime.time object.

    Args:
        time_str (str): Time string like '12:00', '15:35', or '00:00'.

    Returns:
        datetime.time: Corresponding time object.
    """
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError as e:
        raise ValueError(f"Invalid time format: {time_str}") from e