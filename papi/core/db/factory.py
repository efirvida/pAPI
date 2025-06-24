from typing import Dict, Type

from papi.core.models.db.base import BackendSettings
from papi.core.models.db.mongodb import MongoDBEngineConfig
from papi.core.models.db.redis import RedisEngineConfig
from papi.core.models.db.sql import SQLAlchemyEngineConfig

BACKEND_MODEL_REGISTRY: Dict[str, Type[BackendSettings]] = {
    "sqlalchemy": SQLAlchemyEngineConfig,
    "redis": RedisEngineConfig,
    "mongodb": MongoDBEngineConfig,
}


def load_backend_config(name: str, config: dict) -> BackendSettings:
    """
    Factory function to load the appropriate backend config model
    based on the backend name.

    Args:
        name (str): The name of the backend (e.g., 'sqlalchemy').
        config (dict): The raw dictionary configuration.

    Returns:
        BackendSettings: A properly typed and validated backend config model.
    """
    model_cls = BACKEND_MODEL_REGISTRY.get(name, BackendSettings)
    return model_cls(**config)
