from loguru import logger

from papi.core.db import get_redis_client
from user_auth_system.config import security

from .audit import log_security_event_async
from .enums import AuditLogKeys


async def reset_failed_attempts(ip_address: str, username: str):
    """Resets failed attempt counters for an IP-username combination.

    Args:
        ip_address: Client IP address
        username: User identifier

    Clears both the attempt counter and any active account lock.
    """
    redis_client = await get_redis_client()
    await redis_client.delete(f"login_attempts:{ip_address}:{username}")
    await redis_client.delete(f"account_lock:{username}")


async def has_excessive_failed_attempts(username: str) -> bool:
    """Checks if an account is locked due to excessive failed attempts.

    Args:
        username: User identifier to check

    Returns:
        bool: True if account is locked, False otherwise
    """
    redis_client = await get_redis_client()
    lock_key = f"account_lock:{username}"
    return await redis_client.exists(lock_key) == 1


async def record_failed_attempt(ip_address: str, username: str):
    """Records a failed login attempt and triggers account lockout if threshold reached.

    Args:
        ip_address: Client IP address
        username: User identifier

    Uses Redis to track failed attempts with expiration. When attempt threshold
    is reached, locks the account for a configured duration.
    """
    key = f"login_attempts:{ip_address}:{username}"
    redis_client = await get_redis_client()
    attempts = await redis_client.incr(key)
    await redis_client.expire(key, security.lockout_duration_minutes * 60)

    logger.debug(
        f"Failed login attempt #{attempts} for user '{username}' from IP {ip_address}"
    )

    if attempts >= security.max_login_attempts:
        lock_key = f"account_lock:{username}"
        await redis_client.setex(
            lock_key, security.lockout_duration_minutes * 60, "locked"
        )

        logger.info(
            f"Account for user '{username}' locked after {attempts} failed attempts from IP {ip_address}"
        )

        await log_security_event_async(
            AuditLogKeys.ACCOUNT_LOCKED,
            details={"username": username, "ip": ip_address, "attempts": attempts},
        )


async def is_system_locked_out() -> bool:
    """Checks if the system is in global lockout mode.

    Returns:
        bool: True if system lockout is active, False otherwise
    """
    redis_client = await get_redis_client()
    return await redis_client.exists("global_lockout") == 1


async def activate_system_lockout():
    """Activates system-wide authentication lockout for a fixed duration.

    Used as a security measure during suspected brute-force attacks.
    Logs the event to the security audit system.
    """
    redis_client = await get_redis_client()
    await redis_client.setex("global_lockout", 900, "locked")
    await log_security_event_async(AuditLogKeys.SYSTEM_LOCKOUT)
