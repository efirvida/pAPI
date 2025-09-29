import ssl
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, Field, field_validator

from .db.main import DatabaseConfig


class StorageConfig(BaseModel):
    """
    Configuration for storage backends.
    Extra fields are allowed and will be preserved.
    """

    class Config:
        extra = "allow"


class AppsConfig(BaseModel):
    """
    Configuration for the plugin/app system.

    Attributes:
        apps_dir (str): Filesystem path to apps directory.
        enabled (List[str]): List of enabled app identifiers.
        config (Dict[str, Dict[str, Any]]): Custom configuration per app.

    Example:
        ```python
        AppsConfig(
            apps_dir="/opt/apps",
            enabled=["image_storage", "auth"],
            config={"image_storage": {"quality": 90}, "auth": {"provider": "oauth2"}},
        )
        ```
    """

    apps_dir: str = Field(..., description="Path to apps directory")
    enabled: List[str] = Field(default_factory=list, description="List of enabled apps")
    config: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="App-specific configuration dictionary"
    )


class FastAPIAppConfig(BaseModel):
    """
    Configuration model for FastAPI application metadata and settings.

    This model defines metadata and behavioral options that are passed to the FastAPI constructor.
    It supports OpenAPI documentation configuration, middleware injection, server settings, and more.

    Attributes:
        title (Optional[str]): The title of the application, displayed in API docs and UIs.
        summary (Optional[str]): A short summary of the application.
        description (Optional[str]): A detailed description of the application, shown in docs.
        terms_of_service (Optional[str]): A URL to the terms of service for the API.
        license_info (Optional[Dict[str, Union[str, Any]]]): A dictionary specifying the license of the API.
        contact (Optional[Dict[str, Union[str, Any]]]): Contact information for the API maintainer.
        version (Optional[str]): The application version string.

        middleware (Optional[Sequence[str]]): A list of middleware identifiers to include in the app.

        servers (Optional[List[Dict[str, Union[str, Any]]]]): A list of server configurations for OpenAPI docs.
        root_path (Optional[str]): The root path where the app is mounted.
        root_path_in_servers (Optional[bool]): Whether to include the root path in OpenAPI server URLs.

        openapi_url (Optional[str]): The path where the OpenAPI schema will be served. Set to None to disable.
        openapi_tags (Optional[List[Dict[str, Any]]]): A list of tag definitions for organizing endpoints.
        docs_url (Optional[str]): The path to serve Swagger UI documentation. Set to None to disable.
        redoc_url (Optional[str]): The path to serve ReDoc documentation. Set to None to disable.
        swagger_ui_parameters (Optional[Dict[str, Any]]): Additional parameters to customize Swagger UI.

    Notes:
        - Extra fields are allowed and will be preserved.
        - Use the `defined_fields()` method to get only explicitly configured values.

    Example:
        ```python
        config = FastAPIAppConfig(title="My API", version="1.0.0")
        fastapi_app = FastAPI(**config.defined_fields())
        ```
    """

    title: Optional[str] = "pAPI Platform"
    summary: Optional[str] = None
    description: Optional[str] = "pAPI core API Platform"
    terms_of_service: Optional[str] = None
    license_info: Optional[Dict[str, Union[str, Any]]] = None
    contact: Optional[Dict[str, Union[str, Any]]] = None
    version: Optional[str] = ""

    middleware: Optional[Sequence[str]] = []

    servers: Optional[List[Dict[str, Union[str, Any]]]] = None
    root_path: Optional[str] = None
    root_path_in_servers: Optional[bool] = None

    openapi_url: Optional[str] = None
    openapi_tags: Optional[List[Dict[str, Any]]] = None
    docs_url: Optional[str] = None
    redoc_url: Optional[str] = None
    swagger_ui_parameters: Optional[Dict[str, Any]] = None

    model_config = {
        "extra": "allow",
        "populate_by_name": True,
    }

    def defined_fields(self) -> Dict[str, Any]:
        """
        Returns a dictionary with only the fields that have been explicitly set by the user,
        excluding default values and unset or None fields.

        Useful when passing configuration to FastAPI or related tools.

        Returns:
            Dict[str, Any]: A dictionary of defined configuration fields.
        """
        return self.model_dump(
            exclude_unset=True,
            exclude_defaults=True,
            exclude_none=True,
        )


class UvicornServerConfig(BaseModel):
    """
    Configuration model for Uvicorn server runtime.

    This model encapsulates all server-level parameters that can be passed to `uvicorn.run()`.
    It supports fine-grained control over networking, protocol, concurrency,
    SSL, live-reload, and more.

    Attributes:
        host (str): The hostname or IP address where the server will bind.
        port (int): The TCP port where the server will listen (must be between 1 and 65535).
        uds (Optional[Union[str, Path]]): Unix domain socket path to bind instead of host/port.
        fd (Optional[int]): File descriptor to bind instead of host/port/uds.
        loop (str): Event loop implementation to use (e.g., "auto", "uvloop", "asyncio").
        http (Union[str, type]): HTTP protocol class or string identifier.
        ws (Union[str, type]): WebSocket protocol class or string identifier.
        ws_max_size (int): Maximum size for incoming WebSocket messages.
        ws_max_queue (int): Maximum number of messages allowed in receive queue.
        ws_ping_interval (Optional[float]): Interval in seconds to send ping frames.
        ws_ping_timeout (Optional[float]): Timeout for WebSocket pings.
        ws_per_message_deflate (bool): Enable per-message compression for WebSockets.
        lifespan (str): Lifespan handling mode: "auto", "on", or "off".
        env_file (Optional[Union[str, Path]]): Path to a `.env` file with environment variables.
        interface (str): Server interface type ("auto", "asgi3", "asgi2", or "wsgi").
        reload (bool): Enable auto-reload in development mode.
        reload_dirs (Optional[Union[str, List[str]]]): Directories to watch for reload.
        reload_delay (float): Delay in seconds before reloading after changes.
        reload_includes (Optional[Union[str, List[str]]]): Glob patterns to include in reload.
        reload_excludes (Optional[Union[str, List[str]]]): Glob patterns to exclude from reload.
        workers (Optional[int]): Number of worker processes to spawn.
        proxy_headers (bool): Trust proxy headers (e.g., `X-Forwarded-For`).
        server_header (bool): Send the `Server` header in responses.
        date_header (bool): Send the `Date` header in responses.
        forwarded_allow_ips (Optional[Union[str, List[str]]]): List or string of IPs allowed to set forwarded headers.
        root_path (str): Root path to mount the application under.
        limit_concurrency (Optional[int]): Maximum number of concurrent connections.
        limit_max_requests (Optional[int]): Maximum number of requests before a worker is restarted.
        backlog (int): Maximum number of pending connections.
        timeout_keep_alive (int): Keep-alive timeout in seconds.
        timeout_notify (int): Timeout to notify of graceful shutdown.
        timeout_graceful_shutdown (Optional[int]): Max time allowed for graceful shutdown.
        ssl_keyfile (Optional[Union[str, Path]]): Path to the SSL key file.
        ssl_certfile (Optional[Union[str, Path]]): Path to the SSL certificate file.
        ssl_keyfile_password (Optional[str]): Password for the SSL key file, if encrypted.
        ssl_version (int): SSL protocol version (e.g., `ssl.PROTOCOL_TLS`).
        ssl_cert_reqs (int): Whether client certificates are required.
        ssl_ca_certs (Optional[str]): Path to CA certificates file.
        ssl_ciphers (str): String of ciphers to use for SSL connections.
        headers (Optional[List[Tuple[str, str]]]): List of custom headers to add to responses.
        h11_max_incomplete_event_size (Optional[int]): Limit for HTTP/1.1 incomplete event size.

    Notes:
        - Extra fields are allowed and will be preserved.
        - Use the `defined_fields()` method to retrieve only explicitly set values.

    Example:
        ```python
        config = UvicornServerConfig(host="0.0.0.0", port=8080, reload=True)
        uvicorn.run(app, **config.defined_fields())
        ```
    """

    host: str = Field(
        default="127.0.0.1", description="Hostname or IP address to bind the server."
    )
    port: int = Field(
        default=8000,
        description="Port to bind the server (must be between 1 and 65535).",
    )

    uds: Optional[Union[str, Path]] = None
    fd: Optional[int] = None
    loop: str = "auto"
    http: Union[str, type] = "auto"
    ws: Union[str, type] = "auto"
    ws_max_size: int = 16 * 1024 * 1024
    ws_max_queue: int = 32
    ws_ping_interval: Optional[float] = 20.0
    ws_ping_timeout: Optional[float] = 20.0
    ws_per_message_deflate: bool = True
    lifespan: str = "auto"
    env_file: Optional[Union[str, Path]] = None
    access_log: bool = True
    use_colors: Optional[bool] = None
    interface: str = "auto"
    reload: bool = False
    reload_dirs: Optional[Union[str, List[str]]] = None
    reload_delay: float = 0.25
    reload_includes: Optional[Union[str, List[str]]] = None
    reload_excludes: Optional[Union[str, List[str]]] = None
    workers: Optional[int] = None
    proxy_headers: bool = True
    server_header: bool = True
    date_header: bool = True
    forwarded_allow_ips: Optional[Union[str, List[str]]] = None
    root_path: str = ""
    limit_concurrency: Optional[int] = None
    limit_max_requests: Optional[int] = None
    backlog: int = 2048
    timeout_keep_alive: int = 5
    timeout_notify: int = 30
    timeout_graceful_shutdown: Optional[int] = None
    ssl_keyfile: Optional[Union[str, Path]] = None
    ssl_certfile: Optional[Union[str, Path]] = None
    ssl_keyfile_password: Optional[str] = None
    ssl_version: int = ssl.PROTOCOL_TLS
    ssl_cert_reqs: int = ssl.CERT_NONE
    ssl_ca_certs: Optional[str] = None
    ssl_ciphers: str = "TLSv1"
    headers: Optional[List[Tuple[str, str]]] = None
    h11_max_incomplete_event_size: Optional[int] = None

    model_config = {
        "extra": "allow",
        "populate_by_name": True,
    }

    def defined_fields(self) -> dict:
        """
        Return only the fields explicitly defined by the user,
        excluding unset fields, defaults, and None values.

        Returns:
            dict: A dictionary with the explicitly set configuration fields.
        """
        return self.model_dump(
            exclude_unset=True,
            exclude_defaults=True,
            exclude_none=True,
        )

    @field_validator("port")
    def validate_port(cls, v: int) -> int:
        """Ensure that the port is within the valid range (1–65535)."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v


class ServerType(StrEnum):
    """
    Available server types.

    Enum:
        GRANIAN: Granian ASGI server (Rust-based, high performance).
        UVICORN: Uvicorn ASGI server (Python-based, standard).
    """

    GRANIAN = "granian"
    UVICORN = "uvicorn"


class GranianServerConfig(BaseModel):
    """
    Configuration model for Granian server runtime.

    This model encapsulates all server-level parameters that can be passed to Granian.
    Granian is a Rust-based ASGI server with high performance.

    Attributes:
        host (str): The hostname or IP address where the server will bind.
        port (int): The TCP port where the server will listen (must be between 1 and 65535).
        workers (int): Number of worker processes to spawn.
        threads (int): Number of threads per worker.
        interface (str): Server interface type ("asgi" or "wsgi").
        http (str): HTTP version to use ("auto", "1", or "2").
        ws (bool): Enable WebSocket support.
        reload (bool): Enable auto-reload in development mode.
        reload_dir (Optional[str]): Directory to watch for reload.
        ssl_cert (Optional[Union[str, Path]]): Path to the SSL certificate file.
        ssl_key (Optional[Union[str, Path]]): Path to the SSL key file.
        backlog (int): Maximum number of pending connections.
        log_level (str): Log level ("debug", "info", "warning", "error", "critical").
        access_log (bool): Enable access logging.
        url_path_prefix (Optional[str]): URL path prefix for the application.

    Notes:
        - Extra fields are allowed and will be preserved.
        - Use the `defined_fields()` method to retrieve only explicitly set values.

    Example:
        ```python
        config = GranianServerConfig(host="0.0.0.0", port=8080, workers=4)
        granian.run(app, **config.defined_fields())
        ```
    """

    host: str = Field(default="127.0.0.1", description="Host to bind the server to")
    port: int = Field(default=8000, description="Port to bind the server to")
    workers: int = Field(default=1, description="Number of worker processes")
    threads: int = Field(default=1, description="Number of threads per worker")
    interface: str = Field(
        default="asgi", description="Server interface type (asgi or wsgi)"
    )
    http: str = Field(default="auto", description="HTTP version (auto, 1, or 2)")
    ws: bool = Field(default=True, description="Enable WebSocket support")
    reload: bool = Field(default=False, description="Enable auto-reload in development")
    reload_dir: Optional[str] = Field(
        default=None, description="Directory to watch for reload"
    )
    ssl_cert: Optional[Union[str, Path]] = Field(
        default=None, description="Path to SSL certificate file"
    )
    ssl_key: Optional[Union[str, Path]] = Field(
        default=None, description="Path to SSL key file"
    )
    backlog: int = Field(default=1024, description="Maximum pending connections")
    log_level: str = Field(default="info", description="Log level")
    access_log: bool = Field(default=False, description="Enable access logging")
    url_path_prefix: Optional[str] = Field(default=None, description="URL path prefix")

    model_config = {
        "extra": "allow",
        "populate_by_name": True,
    }

    def defined_fields(self) -> dict:
        """
        Return only the fields explicitly defined by the user,
        excluding unset fields, defaults, and None values.

        Returns:
            dict: A dictionary with the explicitly set configuration fields.
        """
        return self.model_dump(
            exclude_unset=True,
            exclude_defaults=True,
            exclude_none=True,
        )

    @field_validator("port")
    def validate_port(cls, v: int) -> int:
        """Ensure that the port is within the valid range (1–65535)."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v


class ServerConfig(BaseModel):
    """
    Unified server configuration that supports multiple server backends.

    Attributes:
        type (ServerType): Server type to use (granian or uvicorn).
        granian (Optional[GranianServerConfig]): Granian-specific configuration.
        uvicorn (Optional[UvicornServerConfig]): Uvicorn-specific configuration.
    """

    type: ServerType = Field(
        default=ServerType.GRANIAN, description="Server type to use"
    )
    granian: Optional[GranianServerConfig] = Field(
        default_factory=GranianServerConfig, description="Granian server configuration"
    )
    uvicorn: Optional[UvicornServerConfig] = Field(
        default=None, description="Uvicorn server configuration"
    )

    def get_server_config(self) -> Union[GranianServerConfig, UvicornServerConfig]:
        """
        Get the appropriate server configuration based on the selected type.

        Returns:
            Union[GranianServerConfig, UvicornServerConfig]: Server configuration.
        """
        if self.type == ServerType.GRANIAN:
            return self.granian or GranianServerConfig()
        else:
            return self.uvicorn or UvicornServerConfig()


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
        apps (AppsConfig): Plugin system configuration.
        storage (StorageConfig): Paths for file/image storage.

    Example:
        ```python
        AppConfig(
            logger=LoggerConfig(level="INFO"),
            info=GeneralInfoConfig(title="My API"),
            server=ServerConfig(host="0.0.0.0", port=8080),
            database=DatabaseConfig(sql_uri="sqlite:///./db.sqlite"),
            apps=AppsConfig(apps_dir="./apps", enabled=[]),
            storage=StorageConfig(files="/data/files"),
        )
        ```
    """

    logger: LoggerConfig
    info: FastAPIAppConfig
    server: ServerConfig
    apps: AppsConfig
    database: DatabaseConfig | None = None
    storage: StorageConfig | None = None
