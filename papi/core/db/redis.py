from typing import Optional
from urllib.parse import urlparse, urlunparse

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


async def get_redis_client() -> Redis | None:
    """
    Lazily initialize and return a singleton Redis client.

    Uses the Redis URI configured in the application settings.

    Returns:
        Redis: An asyncio-compatible Redis client instance.
    """
    global _redis
    config = get_config()
    if _redis is None:
        if config.database and config.database.redis_uri:
            _redis = from_url(
                config.database.redis_uri,
                decode_responses=True,
            )
    return _redis
