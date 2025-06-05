"""
Redis cache implementation for image storage module.
Uses the global Redis client from papi.core.db.
"""

import json
from typing import Any, Dict, Optional

from loguru import logger

from papi.core.db import get_redis_client

from .config import images_settings

# Cache configuration
CACHE_TTL = images_settings.cache_ttl
CACHE_PREFIX = images_settings.cache_prefix


async def get_cached_image_info(image_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve image metadata from Redis cache.

    Args:
        image_id (str): The UUID of the image to retrieve

    Returns:
        Optional[dict]: The cached image metadata or None if not found

    Note:
        Uses the global Redis client from papi.core.db
    """
    try:
        redis = await get_redis_client()
        cached_data = await redis.get(f"{CACHE_PREFIX}{image_id}")
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"Failed to retrieve from cache: {e}")
        # Let the system fallback to database
    return None


async def set_cached_image_info(image_id: str, data: Dict[str, Any]) -> bool:
    """
    Store image metadata in Redis cache.

    Args:
        image_id (str): The UUID of the image
        data (Dict[str, Any]): The image metadata to cache

    Returns:
        bool: True if cached successfully, False otherwise

    Note:
        Sets TTL automatically based on CACHE_TTL configuration
    """
    try:
        redis = await get_redis_client()
        await redis.set(
            f"{CACHE_PREFIX}{image_id}",
            json.dumps(data),
            ex=CACHE_TTL,
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to store in cache: {e}")
        return False


async def invalidate_image_cache(image_id: str) -> None:
    """
    Remove image metadata from cache.

    Args:
        image_id (str): The UUID of the image to remove from cache

    Note:
        Silently fails if the key doesn't exist
    """
    try:
        redis = await get_redis_client()
        await redis.delete(f"{CACHE_PREFIX}{image_id}")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")


async def clear_all_image_cache() -> None:
    """
    Clear all image metadata from cache.

    This is useful for maintenance or when needing to force a refresh
    of all cached data.
    """
    try:
        redis = await get_redis_client()
        keys = await redis.keys(f"{CACHE_PREFIX}*")
        if keys:
            await redis.delete(*keys)
    except Exception as e:
        logger.warning(f"Failed to clear image cache: {e}")
