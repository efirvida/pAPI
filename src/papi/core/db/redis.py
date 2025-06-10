from typing import Optional
from urllib.parse import urlparse, urlunparse

from redis.asyncio import Redis, from_url

from papi.core.settings import get_config

_redis: Optional[Redis] = None


def get_redis_uri_with_db(base_uri: str, db_index: int) -> str:
    parsed = urlparse(base_uri)
    new_path = f"/{db_index}"
    return urlunparse(parsed._replace(path=new_path))


async def get_redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(
            get_config().database.redis_uri,
            decode_responses=True,
        )
    return _redis
