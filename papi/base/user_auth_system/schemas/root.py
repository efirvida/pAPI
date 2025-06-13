import re
from typing import Self

from loguru import logger
from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RootUserEnv(BaseSettings):
    """Root user environment configuration.

    This class manages the configuration for the root/admin user account.
    It loads settings from environment variables with fallback defaults.

    Security Note:
        The default values are intentionally weak and should be changed
        in production environments using environment variables.

    Environment Variables:
        ROOT_USERNAME: Username for the root user (default: "root")
        ROOT_USER_EMAIL: Email address for the root user (default: "root@papi.com")
        ROOT_USER_PASSWORD: Password for the root user (default: "root")
        ROOT_ROLE_NAME: Role name for the root user (default: "root")
    """

    username: str = Field(
        default="root",
        validation_alias="ROOT_USERNAME",
        description="Username for the root user account",
        min_length=1,
        max_length=50,
    )

    email: EmailStr = Field(
        default="root@papi.com",
        validation_alias="ROOT_USER_EMAIL",
        description="Email address for the root user account",
    )

    password: str = Field(
        default="root",
        validation_alias="ROOT_USER_PASSWORD",
        description="Password for the root user account",
        min_length=1,
    )

    role_name: str = Field(
        default="root",
        validation_alias="ROOT_ROLE_NAME",
        description="Role name assigned to the root user",
        min_length=1,
        max_length=50,
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    @field_validator("username", "role_name", mode="before")
    @classmethod
    def validate_alphanumeric_fields(cls, v: str, info) -> str:
        """Validate that username and role_name contain only safe characters."""
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty or whitespace-only")

        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError(
                f"{info.field_name} can only contain letters, numbers, underscores, hyphens, and dots"
            )

        return v

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password and warn about weak defaults."""
        v = v.strip()
        if not v:
            raise ValueError("Password cannot be empty or whitespace-only")

        weak_passwords = {"root", "admin", "password", "123456", "password123"}
        if v.lower() in weak_passwords:
            logger.warning(
                "Using a weak default password! Please set ROOT_USER_PASSWORD "
                "environment variable with a strong password for production use.",
            )

        if len(v) < 8:
            logger.warning(
                "Password is shorter than 8 characters. Consider using a longer password "
                "for better security.",
            )

        return v

    @model_validator(mode="after")
    def validate_security_settings(self) -> Self:
        """Perform cross-field validation and security checks."""
        if self.email == "root@papi.com":
            logger.warning(
                "Using default email address! Please set ROOT_USER_EMAIL "
                "environment variable with a valid email for production use.",
            )

        if self.username == self.password:
            raise ValueError("Username and password cannot be the same")

        if self.role_name == self.password:
            raise ValueError("Role name and password cannot be the same")

        return self

    def is_using_defaults(self) -> dict[str, bool]:
        """Check which fields are using default values."""
        return {
            "username": self.username == "root",
            "email": self.email == "root@papi.com",
            "password": self.password == "root",
            "role_name": self.role_name == "root",
        }

    def get_security_warnings(self) -> list[str]:
        """Get a list of security warnings for current configuration."""
        warnings_list = []
        defaults = self.is_using_defaults()

        if defaults["password"]:
            warnings_list.append("Using default password 'root' - change immediately!")

        if defaults["email"]:
            warnings_list.append(
                "Using default email 'root@papi.com' - update for production"
            )

        if len(self.password) < 8:
            warnings_list.append("Password is too short - use at least 8 characters")

        if self.password.lower() in {"root", "admin", "password", "123456"}:
            warnings_list.append(
                "Password is too common - use a unique strong password"
            )

        return warnings_list
