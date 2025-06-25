from typing import Optional
from urllib.parse import urlparse, urlunparse

from loguru import logger
from redis.asyncio import Redis, from_url

from papi.core.settings import get_config

_redis: Optional[Redis] = None


def get_redis_uri_with_db(base_uri: str, db_index: int) -> str:
    """
    Construct a Redis URI with a specific database index.

    Args:
        base_uri (str): The base Redis URI, without the database path.
        db_index (int): The database index to use (e.g., 0, 1, 2...).

    Returns:
        str: The Redis URI with the database index set as the path.
    """
    parsed = urlparse(base_uri)
    new_path = f"/{db_index}"
    return urlunparse(parsed._replace(path=new_path))


async def get_redis_client() -> Optional[Redis]:
    """
    Lazily initialize and return a singleton Redis client.

    Uses the Redis URI configured in the application settings.

    Returns:
        Redis: An asyncio-compatible Redis client instance.
    """
    global _redis
    if _redis is not None:
        logger.debug("Reusing existing Redis client.")
        return _redis

    config = get_config()
    redis_backend = None

    if config.database:
        redis_backend = config.database.get_backend("redis")
        return None

    if not redis_backend or not redis_backend.url:
        logger.warning(
            "Redis URI is not configured. Redis client will not be initialized."
        )
        return None

    logger.info("Initializing Redis client...")
    logger.debug("Redis backend config: {}", redis_backend.get_defined_fields())

    try:
        _redis = from_url(**redis_backend.get_defined_fields())
        logger.success("Redis client initialized successfully.")
    except Exception as e:
        logger.exception("Failed to initialize Redis client: {}", e)
        _redis = None

    return _redis
