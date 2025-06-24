from typing import Any, Dict

from pydantic import BaseModel, Field


class BackendSettings(BaseModel):
    """
    Advanced settings for a database backend.

    All backends must provide a `uri`, which is the main connection string.
    Additional backend-specific configuration (e.g., connect_args, auth, pool size)
    can be passed freely, as this model allows extra fields.

    This structure enforces a consistent configuration interface across different
    backends, while still supporting flexible and extensible parameters.

    Attributes:
        uri (str): The database connection URI.

    Example:
        ```yaml
        database:
          backends:
            sqlalchemy:
              uri: "postgresql+asyncpg://user:pass@localhost/db"
              execution_options:
                isolation_level: "READ COMMITTED"
            redis:
              uri: "redis://localhost:6379/0"
              socket_timeout: 5
        ```
    """

    url: str = Field(..., description="DB connection URI (required)")

    class Config:
        extra = "allow"

    def get_defined_fields(self) -> Dict[str, Any]:
        """
        Returns:
            dict: A dictionary of fields that were explicitly defined (not defaults).
        """
        return self.model_dump(exclude_unset=True)
