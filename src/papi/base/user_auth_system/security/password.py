import re

import bcrypt
from fastapi import HTTPException, status

from . import auth_settings, security

MIN_PASSWORD_LENGTH = auth_settings.password_min_length
PASSWORD_VALIDATION_RULES = [
    (r"[A-Z]", "at least one uppercase letter"),
    (r"[a-z]", "at least one lowercase letter"),
    (r"\d", "at least one digit"),
    (r"[!@#$%^&*(),.?\":{}|<>]", "at least one special character"),
]


def hash_password(password: str) -> str:
    """Generates a bcrypt hash with configurable work factor.

    Args:
        password: Plaintext password to hash

    Returns:
        str: Bcrypt-hashed password string

    Raises:
        ValueError: If password is invalid or too short

    The bcrypt work factor (rounds) is controlled by security configuration.
    """
    if not isinstance(password, str):
        if not security.allow_weak_passwords:
            validate_password_strength(password)

    salt = bcrypt.gensalt(rounds=security.bcrypt_rounds)
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Securely verifies a password against a stored hash.

    Args:
        plain_password: Password to verify
        hashed_password: Stored bcrypt hash to compare against

    Returns:
        bool: True if passwords match, False otherwise

    Uses constant-time comparison to prevent timing attacks. Returns False
    immediately if either input is empty.
    """
    if not plain_password or not hashed_password:
        return False

    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def validate_password_strength(password: str) -> None:
    """Validates password against configured complexity rules.

    Args:
        password: Password to validate

    Raises:
        HTTPException: If password doesn't meet strength requirements

    Bypasses validation if weak passwords are allowed in configuration.
    Checks length, character diversity, and special character requirements.
    """
    if security.allow_weak_passwords:
        return

    errors = []

    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )

    for pattern, message in PASSWORD_VALIDATION_RULES:
        if not re.search(pattern, password):
            errors.append(f"Password must contain {message}")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(errors),
        )
