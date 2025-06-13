from loguru import logger

from papi.core.db import get_redis_client

# Time-to-live for cached user data in seconds
CACHE_TTL_SECONDS = 60


async def cache_user(username: str, user_json: str):
    """
    Caches the serialized user data in Redis with a time-to-live.

    Args:
        username (str): The unique identifier (e.g., username or ID) of the user.
        user_json (str): The JSON-serialized representation of the user data.

    Notes:
        The cached value will expire after `CACHE_TTL_SECONDS`.
        In case of failure, the exception is logged but not raised.
    """
    redis = await get_redis_client()
    try:
        await redis.set(f"user_cache:{username}", user_json, ex=CACHE_TTL_SECONDS)
        logger.debug(f"User {username} cached successfully")
    except Exception as e:
        logger.warning(f"Failed to cache user {username}: {e}")


async def get_cached_user(username: str) -> str | None:
    """
    Retrieves cached user data from Redis.

    Args:
        username (str): The unique identifier of the user whose data is being retrieved.

    Returns:
        Optional[str]: The JSON-serialized user data if it exists in the cache,
        otherwise `None`.

    Notes:
        This function does not raise exceptions; it assumes Redis availability has been handled upstream.
    """
    redis = await get_redis_client()
    try:
        cached_data = await redis.get(f"user_cache:{username}")
        if cached_data is not None:
            logger.debug(f"Cache hit for user {username}")
        else:
            logger.debug(f"Cache miss for user {username}")
        return cached_data
    except Exception as e:
        logger.warning(f"Failed to retrieve cached user {username}: {e}")
        return None
