from typing import Annotated, List

from pydantic import BaseModel, Field, SecretStr, field_validator


class KeyRotation(BaseModel):
    """
    Configuration for JWT key rotation settings.

    Attributes:
        enabled: Flag to enable/disable automatic key rotation
        rotation_interval_days: Days between automatic key rotations
        max_historical_keys: Maximum historical keys to retain
    """

    enabled: bool = Field(
        default=True, description="Enable automatic periodic key rotation"
    )
    rotation_interval_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days between automatic key rotations (min 1, max 365)",
    )
    max_historical_keys: int = Field(
        default=5,
        ge=1,
        le=12,
        description="Maximum historical keys to retain (min 1, max 12)",
    )


class BaseSecurity(BaseModel):
    """
    Core security configuration for authentication system.

    Security Settings:
        secret_key: Cryptographic secret for token signing
        token_issuer: JWT issuer claim
        token_audience: JWT audience claim
        key_rotation: Key rotation configuration
        access_token_expire_minutes: Access token validity period
        allow_weak_passwords: Flag to allow insecure passwords
        bcrypt_rounds: Bcrypt hashing complexity
        hash_algorithm: JWT signing algorithm
        max_login_attempts: Failed attempts before lockout
        lockout_duration_minutes: Account lockout period
    """

    secret_key: SecretStr = Field(
        ...,
        min_length=64,
        description="Cryptographic secret for token signing (min 64 chars)",
    )
    token_issuer: str = Field(
        default="auth-system",
        min_length=3,
        description="JWT issuer claim (usually your domain)",
    )
    token_audience: str = Field(
        default="client-app",
        min_length=3,
        description="JWT audience claim (client application identifier)",
    )
    key_rotation: KeyRotation = Field(
        default_factory=KeyRotation, description="JWT key rotation configuration"
    )
    access_token_expire_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Access token validity in minutes (5 min - 24 hours)",
    )
    allow_weak_passwords: bool = Field(
        default=False, description="Allow insecure passwords (not recommended)"
    )
    bcrypt_rounds: int = Field(
        default=12,
        ge=5,
        le=15,
        description="Bcrypt hashing complexity rounds (security vs performance)",
    )
    hash_algorithm: str = Field(
        default="HS256",
        pattern="^(HS256|HS384|HS512|RS256|RS384|RS512|ES256|ES384)$",
        description="JWT signing algorithm (recommended: HS256, RS256)",
    )
    max_login_attempts: int = Field(
        default=5,
        ge=3,
        le=10,
        description="Failed login attempts before account lockout",
    )
    lockout_duration_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Account lockout duration in minutes (1 min - 24 hours)",
    )


class AuthSettings(BaseModel):
    """
    Application authentication configuration settings.

    Attributes:
        security: Core security configuration
        allow_registration: Enable user registration
        password_min_length: Minimum password length
        default_user_roles: Default roles assigned to new users
    """

    security: BaseSecurity = Field(..., description="Core security configuration")
    allow_registration: bool = Field(
        default=True, description="Enable new user registration"
    )
    password_min_length: int = Field(
        default=12,
        ge=8,
        le=128,
        description="Minimum password length (8-128 characters)",
    )
    default_user_roles: Annotated[
        List[str],
        Field(min_length=1, description="Default roles assigned to new users"),
    ] = ["user"]

    @field_validator("default_user_roles", mode="before")
    def normalize_user_roles(cls, value) -> list:
        """Normalize role input to list format."""
        if value is None:
            return ["user"]
        if isinstance(value, str):
            return [role.strip() for role in value.split(",") if role.strip()]
        return value

    @field_validator("default_user_roles")
    def validate_user_roles(cls, value: list) -> list:
        """Validate and deduplicate roles."""
        if not value:
            raise ValueError("At least one default role is required")

        validated_roles = []
        for role in value:
            clean_role = role.strip()
            if not clean_role:
                raise ValueError("Role names cannot be empty")
            if clean_role not in validated_roles:
                validated_roles.append(clean_role)

        return validated_roles


class Token(BaseModel):
    """
    JWT token response model.

    Attributes:
        access_token: Short-lived access token
        refresh_token: Long-lived refresh token
        token_type: Always 'bearer'
    """

    access_token: str = Field(
        ..., description="Short-lived access token for API authorization"
    )
    refresh_token: str = Field(
        ..., description="Long-lived refresh token for obtaining new access tokens"
    )
    token_type: str = Field(
        default="bearer", description="Token type (always 'bearer')"
    )


class LoginRequest(BaseModel):
    """
    User authentication request model.

    Attributes:
        username: User identifier
        password: User credentials
        device_id: Unique device identifier
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="User identifier (email or username)",
    )
    password: str = Field(..., min_length=8, description="User credentials")
    device_id: str = Field(
        ...,
        min_length=8,
        max_length=36,
        description="Unique device identifier (min 8 chars)",
    )
