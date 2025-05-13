from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, Field, field_validator


class StorageConfig(BaseModel):
    files: Optional[str] = ""
    images: Optional[str] = ""

    class Config:
        extra = Extra.allow


class ServerConfig(BaseModel):
    """Server configuration."""

    host: Optional[str] = Field(
        default="localhost", description="Server hostname or IP"
    )
    port: Optional[int] = Field(default=8000, description="Server port")

    @field_validator("port")
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v


class DatabaseConfig(BaseModel):
    """Database URIs for MongoDB, SQL and Redis."""

    mongodb_uri: Optional[str] = Field(default="", description="MongoDB connection URI")
    redis_uri: Optional[str] = Field(default="", description="Redis connection URI")
    sql_uri: Optional[str] = Field(
        default="", description="SQL (PostgreSQL/MySQL/SQlite) connection URI"
    )


class AddonsConfig(BaseModel):
    """Addon system configuration."""

    extra_addons_path: str = Field(..., description="Path to external addons directory")
    enabled: List[str] = Field(
        default_factory=list, description="List of enabled addons"
    )
    config: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Addon-specific configuration dictionary"
    )


class GeneralInfoConfig(BaseModel):
    title: Optional[str] = "pAPI Platform"


class LoggerLevel(StrEnum):
    INFO = "INFO"
    DEBUG = "DEBUG"


class LoggerConfig(BaseModel):
    level: Optional[LoggerLevel] = LoggerLevel.INFO
    log_file: Optional[str] = None
    json_log: Optional[bool] = False


class AppConfig(BaseModel):
    """Top-level application configuration."""

    logger: LoggerConfig
    info: GeneralInfoConfig
    server: ServerConfig
    database: DatabaseConfig
    addons: AddonsConfig
    storage: StorageConfig
