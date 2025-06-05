import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from loguru import logger
from redis.exceptions import LockError

from papi.core.db import get_redis_client

from . import security
from .audit import log_security_event_async
from .enums import AuditLogKeys
from .key_manager import key_manager


async def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Generates a JWT access token with rotating keys and security headers.

    Args:
        data: Payload data to include in the token
        expires_delta: Optional custom token expiration time

    Returns:
        str: Signed JWT access token

    Implements distributed locking for safe key rotation in multi-instance environments.
    Includes comprehensive security claims in the token payload.
    """
    redis_client = await get_redis_client()
    lock = redis_client.lock("rotate_key_lock", timeout=10, blocking_timeout=1)

    if key_manager.should_rotate():
        try:
            if await lock.acquire():
                if key_manager.should_rotate():
                    logger.info("Rotating JWT signing keys")
                    key_manager.rotate_key()
                    await log_security_event_async(AuditLogKeys.KEY_ROTATION)
        except LockError:
            logger.warning("Failed to acquire lock for key rotation")
        finally:
            try:
                await lock.release()
            except Exception:
                pass

    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expires_delta = expires_delta or timedelta(
        minutes=security.access_token_expire_minutes
    )
    expire = now + expires_delta

    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now - timedelta(seconds=30),
        "iss": security.token_issuer,
        "aud": security.token_audience,
        "typ": "access",
        "sub": to_encode.get("sub", ""),
        "jti": secrets.token_urlsafe(32),
        "kid": str(len(key_manager.all_keys) - 1),
    })

    return jwt.encode(
        to_encode, key_manager.current_key, algorithm=security.hash_algorithm
    )
