import re
from typing import Optional, Tuple


def parse_search_time(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a search time string. Returns (value, error_message).
    """
    if not raw:
        return "ASAP", None

    raw_input = raw.strip().upper()

    if raw_input.isdigit():
        hour = int(raw_input)
        if hour < 0 or hour > 23:
            return None, "Invalid time. Please enter **0–23**, or **7PM / 11AM**."
        return raw_input, None

    if re.fullmatch(r"(1[0-2]|[1-9])(AM|PM)", raw_input):
        return raw_input, None

    return None, (
        "Invalid time format.\n\nValid examples:\n"
        "- `0` → `23`\n"
        "- `7PM`\n"
        "- `11AM`\n\nAll times are ET (GMT-5)."
    )
