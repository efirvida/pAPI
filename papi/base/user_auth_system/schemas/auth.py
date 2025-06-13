from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, field_validator


class KeyRotation(BaseModel):
    """Configuration for JWT key rotation.

    Attributes:
        rotation_interval_days: Number of days between key rotations
        max_historical_keys: Maximum number of old keys to keep
    """

    rotation_interval_days: int = 30
    max_historical_keys: int = 5


class BaseSecurity(BaseModel):
    access_token_expire_minutes: int = 60
    allow_weak_passwords: bool = False
    bcrypt_rounds: int = 5
    hash_algorithm: str = "HS256"
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    secret_key: str
    token_audience: str
    token_issuer: str
    key_rotation: KeyRotation


class AuthSettings(BaseModel):
    security: BaseSecurity
    allow_registration: bool = True
    password_min_length: int = 8
    default_user_roles: Union[List[str], str] = ["user"]

    @field_validator("default_user_roles", mode="before")
    def normalize_user_roles(cls, value) -> list:
        if value is None:
            return ["user"]
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("default_user_roles")
    def validate_user_roles(cls, value: list) -> list:
        if not value:
            raise ValueError("At least one default role is required")

        validated_roles = []
        for role in value:
            clean_role = str(role).strip()
            if not clean_role:
                raise ValueError("Role names cannot be empty or whitespace-only")
            if clean_role not in validated_roles:
                validated_roles.append(clean_role)

        return validated_roles


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: datetime


class TokenData(BaseModel):
    """Data embedded in JWT token.

    Attributes:
        username: The username of the token owner
    """

    username: Optional[str] = None
