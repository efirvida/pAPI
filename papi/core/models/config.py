from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class StorageConfig(BaseModel):
    """
    Configuration for storage backends.

    Attributes:
        files (Optional[str]): Base path or URI for file storage.
        images (Optional[str]): Base path or URI for image storage.

    Extra fields are allowed and will be preserved.
    """

    files: Optional[str] = ""
    images: Optional[str] = ""

    class Config:
        extra = "allow"


class ServerConfig(BaseModel):
    """
    Configuration for the server runtime.

    Attributes:
        host (Optional[str]): Hostname or IP address to bind the server.
        port (Optional[int]): Port to bind the server (must be between 1 and 65535).

    Example:
        ```python
        ServerConfig(host="0.0.0.0", port=8080)
        ```
    """

    host: Optional[str] = Field(
        default="localhost", description="Server hostname or IP"
    )
    port: Optional[int] = Field(default=8000, description="Server port")

    @field_validator("port")
    def validate_port(cls, v):
        """Validate that the port number is in the acceptable range (1–65535)."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v


class DatabaseConfig(BaseModel):
    """
    Connection URIs for supported databases.

    Attributes:
        mongodb_uri (Optional[str]): MongoDB connection string.
        redis_uri (Optional[str]): Redis connection string.
        sql_uri (Optional[str]): SQL database connection string (PostgreSQL, MySQL, or SQLite).

    Extra fields are allowed and will be preserved.

    Example:
        ```python
        DatabaseConfig(
            mongodb_uri="mongodb://localhost:27017",
            redis_uri="redis://localhost:6379",
            sql_uri="postgresql+asyncpg://user:pass@localhost/dbname",
        )
        ```
    """

    mongodb_uri: Optional[str] = Field(default="", description="MongoDB connection URI")
    redis_uri: Optional[str] = Field(default="", description="Redis connection URI")
    sql_uri: Optional[str] = Field(
        default="", description="SQL (PostgreSQL/MySQL/SQlite) connection URI"
    )

    class Config:
        extra = "allow"


class AddonsConfig(BaseModel):
    """
    Configuration for the plugin/addon system.

    Attributes:
        extra_addons_path (str): Filesystem path to external addons.
        enabled (List[str]): List of enabled addon identifiers.
        config (Dict[str, Dict[str, Any]]): Custom configuration per addon.

    Example:
        ```python
        AddonsConfig(
            extra_addons_path="/opt/plugins",
            enabled=["image_storage", "auth"],
            config={"image_storage": {"quality": 90}, "auth": {"provider": "oauth2"}},
        )
        ```
    """

    extra_addons_path: str = Field(..., description="Path to external addons directory")
    enabled: List[str] = Field(
        default_factory=list, description="List of enabled addons"
    )
    config: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Addon-specific configuration dictionary"
    )


class GeneralInfoConfig(BaseModel):
    """
    General information about the application, passed to FastAPI instance.

    Attributes:
        title (Optional[str]): Application title to show in documentation or UIs.

    Extra fields are allowed and will be preserved.
    """

    title: Optional[str] = "pAPI Platform"
    version: Optional[str] = ""
    description: Optional[str] = "pAPI core API Platform"

    class Config:
        extra = "allow"


class LoggerLevel(StrEnum):
    """
    Available logging levels.

    Enum:
        INFO: Informational logs.
        DEBUG: Debug-level logs (more verbose).
    """

    INFO = "INFO"
    DEBUG = "DEBUG"


class LoggerConfig(BaseModel):
    """
    Logging configuration for the application.

    Attributes:
        level (Optional[LoggerLevel]): Logging level (INFO or DEBUG).
        log_file (Optional[str]): Optional path to a log file.
        json_log (Optional[bool]): Whether to output logs in JSON format.

    Example:
        ```python
        LoggerConfig(level="DEBUG", log_file="logs/app.log", json_log=True)
        ```
    """

    level: Optional[LoggerLevel] = LoggerLevel.INFO
    log_file: Optional[str] = None
    json_log: Optional[bool] = False


class AppConfig(BaseModel):
    """
    Top-level application configuration schema.

    Groups all subcomponents of the configuration under named sections.

    Attributes:
        logger (LoggerConfig): Logging configuration.
        info (GeneralInfoConfig): General metadata.
        server (ServerConfig): Server options.
        database (DatabaseConfig): Connection strings for databases.
        addons (AddonsConfig): Plugin system configuration.
        storage (StorageConfig): Paths for file/image storage.

    Example:
        ```python
        AppConfig(
            logger=LoggerConfig(level="INFO"),
            info=GeneralInfoConfig(title="My API"),
            server=ServerConfig(host="0.0.0.0", port=8080),
            database=DatabaseConfig(sql_uri="sqlite:///./db.sqlite"),
            addons=AddonsConfig(extra_addons_path="./addons", enabled=[]),
            storage=StorageConfig(files="/data/files"),
        )
        ```
    """

    logger: LoggerConfig
    info: GeneralInfoConfig
    server: ServerConfig
    addons: AddonsConfig
    database: DatabaseConfig | None = None
    storage: StorageConfig | None = None
