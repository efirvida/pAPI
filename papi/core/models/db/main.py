from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator, root_validator

from papi.core.db.factory import load_backend_config

from .base import BackendSettings


class DatabaseConfig(BaseModel):
    """
    Database configuration supporting both simple and structured modes.

    This model supports two ways to configure your database engines:

    1. Simple Mode:
        Use `mongodb_uri`, `sql_uri`, and `redis_uri` directly for quick setup.

    2. Advanced Mode:
        Use the `backends` field to provide per-backend configuration.

    The simple URIs will be automatically injected into the appropriate
    `backends[...]` entry if not already specified, using a shared `BackendSettings` schema.

    Attributes:
        mongodb_uri (Optional[str]): MongoDB URI (shortcut).
        redis_uri (Optional[str]): Redis URI (shortcut).
        sql_uri (Optional[str]): SQLAlchemy URI (shortcut).
        backends (Dict[str, BackendSettings]): Full per-backend configurations.

    Example:
        ```yaml
        database:
          mongodb_uri: "mongodb://localhost:27017/mydb"
          redis_uri: "redis://localhost:6379"
          sql_uri: "postgresql+asyncpg://localhost/mydb"

          backends:
            sqlalchemy:
              execution_options:
                isolation_level: "READ COMMITTED"
            redis:
              socket_timeout: 3
        ```
    """

    mongodb_uri: Optional[str] = Field(default=None)
    redis_uri: Optional[str] = Field(default=None)
    sql_uri: Optional[str] = Field(default=None)

    backends: Dict[str, BackendSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def hydrate_backends_with_uris(self) -> "DatabaseConfig":
        """
        Automatically populate backend configurations with URIs from top-level fields,
        unless the URI is already specified in the `backends` dict.
        """
        uri_map = {
            "mongodb_uri": "beanie",
            "redis_uri": "redis",
            "sql_uri": "sqlalchemy",
        }

        for field_name, backend_key in uri_map.items():
            uri_value = getattr(self, field_name)
            if uri_value:
                if backend_key not in self.backends:
                    self.backends[backend_key] = BackendSettings(uri=uri_value)
                elif "url" not in self.backends[backend_key].__dict__:
                    # Inject uri into existing backend config if missing
                    self.backends[backend_key].__dict__["url"] = uri_value

        return self

    def get_backend_uri(self, backend: str) -> Optional[str]:
        """
        Returns the URI for a given backend, if available.

        Args:
            backend (str): The backend name (e.g., 'sqlalchemy', 'redis', 'beanie').

        Returns:
            Optional[str]: The URI or None.
        """
        return self.backends.get(backend, BackendSettings(url="")).url or None

    def get_backend(self, backend: str) -> Optional[BackendSettings]:
        """
        Returns the backend, if available.

        Args:
            backend (str): The backend name (e.g., 'sqlalchemy', 'redis', 'beanie').

        """
        return self.backends.get(backend, BackendSettings(url="")) or None

    @root_validator(pre=True)
    def inject_simple_uris_into_backends(cls, values):
        uri_mapping = {
            "mongodb_uri": "beanie",
            "redis_uri": "redis",
            "sql_uri": "sqlalchemy",
        }
        backends = values.get("backends", {})

        for uri_field, backend_name in uri_mapping.items():
            uri = values.get(uri_field)
            if uri:
                backends.setdefault(backend_name, {})  # create if not exists
                backends[backend_name].setdefault("url", uri)

        # Instantiate backend config objects
        values["backends"] = {
            name: load_backend_config(name, config) for name, config in backends.items()
        }
        return values

    class Config:
        extra = "allow"
