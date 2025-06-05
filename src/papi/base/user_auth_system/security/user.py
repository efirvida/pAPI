import re
from typing import Final, Set

FORBIDDEN_TERMS: Final[Set[str]] = {
    "root",
    "admin",
    "superuser",
    "supervisor",
    "support",
    "system",
    "role",
    "group",
}


def validate_username(username: str) -> str:
    """
    Validates a username string to ensure it meets security and formatting rules.

    The username must:
      - Be composed of only letters (a-z, A-Z), digits (0-9), underscores (_) or hyphens (-).
      - Start and end with a letter or digit.
      - May contain a single '_' or '-' between segments (not consecutively).
      - Not include reserved terms such as 'root', 'admin', 'role', etc.

    Args:
        username (str): The username to validate.

    Returns:
        str: The validated username if it meets all conditions.

    Raises:
        ValueError: If the username does not meet the pattern requirements or includes a forbidden term.
    """
    username = username.strip()

    # Validate allowed structure
    pattern = re.compile(r"^[a-zA-Z0-9]+([_-]?[a-zA-Z0-9]+)*$")
    if not pattern.fullmatch(username):
        raise ValueError(
            "Username must be alphanumeric and may include a single '-' or '_' between segments."
        )

    # Check for forbidden terms (case-insensitive)
    lowered = username.lower()
    if any(term in lowered for term in FORBIDDEN_TERMS):
        raise ValueError("Username contains a reserved word.")

    return username
