import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
from fastapi import Request
from jwt import get_unverified_header
from loguru import logger
from redis.exceptions import LockError
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import SQLAlchemyError

from papi.core.db import get_redis_client, get_sql_session
from user_auth_system.config import security
from user_auth_system.models.token import AccessToken, RefreshToken
from user_auth_system.security.jwt_utils import get_signing_key_by_kid, validate_token

from .audit import log_security_event_async
from .enums import AuditLogKeys
from .key_manager import key_manager


async def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generates a JWT access token and revokes previous tokens for the same subject/device.

    Performs key rotation if needed and ensures token uniqueness per device by:
    1. Checking for key rotation requirements
    2. Generating new token metadata
    3. Revoking previous valid tokens for the subject/device
    4. Persisting the new token in the database

    Args:
        data: Dictionary containing token claims (must include 'sub' and 'device_id')
        expires_delta: Optional custom token expiration period

    Returns:
        Encoded JWT access token string

    Raises:
        SQLAlchemyError: If database operations fail
    """
    redis_client = await get_redis_client()
    lock = redis_client.lock("rotate_key_lock", timeout=10, blocking_timeout=1)

    # Handle key rotation if required
    if key_manager.should_rotate():
        try:
            if await lock.acquire():
                if key_manager.should_rotate():
                    logger.info("Rotating JWT signing keys")
                    await key_manager.rotate_key()
                    await log_security_event_async(AuditLogKeys.KEY_ROTATION)
        except LockError:
            logger.warning("Failed to acquire lock for key rotation")
        finally:
            try:
                await lock.release()
            except Exception:
                logger.warning("Failed to release lock after rotation attempt")

    # Prepare token expiration and metadata
    now = datetime.now(timezone.utc)
    expires_delta = expires_delta or timedelta(
        minutes=security.access_token_expire_minutes
    )
    expire = now + expires_delta
    jti = secrets.token_urlsafe(32)  # Unique token identifier
    kid = str(key_manager.current_kid)
    headers = {"kid": kid, "alg": security.hash_algorithm, "typ": "JWT"}
    subject = data["sub"]
    device_id = data["device_id"]
    ttl = 30  # Not-before time buffer

    # Build token payload
    payload = {
        "exp": expire,
        "iat": now,
        "nbf": now - timedelta(seconds=ttl),
        "iss": security.token_issuer,
        "aud": security.token_audience,
        "sub": subject,
        "jti": jti,
        "typ": "access",
        "device_id": device_id,
    }

    async with get_sql_session() as session:
        # Revoke previous tokens for this subject/device
        result = await session.execute(
            select(AccessToken).where(
                AccessToken.subject == subject,
                AccessToken.device_id == device_id,
                AccessToken.revoked.is_(False),
            )
        )
        for token in result.scalars():
            token.revoked = True
            token.revoked_at = now

        # Register new token
        session.add(
            AccessToken(
                jti=jti,
                subject=subject,
                device_id=device_id,
                expires_at=expire,
                revoked=False,
            )
        )
        await session.commit()

    logger.debug(
        f"Generated access token for subject '{subject}' on device '{device_id}'"
    )
    return jwt.encode(
        payload,
        key_manager.current_key,
        algorithm=security.hash_algorithm,
        headers=headers,
    )


async def create_or_replace_refresh_token(
    subject: str,
    device_id: str,
    user_agent: Optional[str] = None,
    expires_in_days: int = 30,
) -> Tuple[str, str, datetime]:
    """
    Generates a new refresh token and revokes previous tokens for the subject/device.

    Ensures only one valid refresh token exists per device by:
    1. Generating new token with unique JTI
    2. Revoking previous valid tokens for the subject/device
    3. Storing the new token hash in the database

    Args:
        subject: User identifier (subject claim)
        device_id: Device identifier
        user_agent: Optional client user agent string
        expires_in_days: Token validity period in days

    Returns:
        Tuple containing:
        - Encoded refresh token string
        - Unique token identifier (JTI)
        - Expiration datetime

    Raises:
        SQLAlchemyError: If database operations fail
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=expires_in_days)
    jti = secrets.token_urlsafe(32)
    kid = key_manager.current_kid
    headers = {"kid": kid, "alg": security.hash_algorithm, "typ": "JWT"}

    # Build token payload
    payload = {
        "exp": expire,
        "iat": now,
        "nbf": now - timedelta(seconds=30),
        "iss": security.token_issuer,
        "aud": security.token_audience,
        "typ": "refresh",
        "sub": subject,
        "jti": jti,
        "device_id": device_id,
    }

    token_str = jwt.encode(
        payload=payload,
        key=key_manager.current_key,
        algorithm=security.hash_algorithm,
        headers=headers,
    )

    async with get_sql_session() as session:
        # Revoke previous refresh tokens
        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.subject == subject,
                RefreshToken.device_id == device_id,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > now,
            )
        )
        for token in result.scalars():
            token.revoked = True
            token.revoked_at = now

        # Register new token
        session.add(
            RefreshToken(
                jti=jti,
                subject=subject,
                token_hash=RefreshToken.compute_token_hash(token_str),
                device_id=device_id,
                user_agent=user_agent,
                expires_at=expire,
                revoked=False,
            )
        )
        await session.commit()

    logger.info(
        f"Generated refresh token for subject '{subject}' on device '{device_id}'"
    )
    return token_str, jti, expire


async def revoke_refresh_token(refresh_jti: str) -> None:
    """
    Revokes a specific refresh token by its unique identifier (JTI).

    Args:
        refresh_jti: Unique token identifier (JTI)

    Returns:
        None

    Note:
        - Assumes jti is globally unique (enforced at database level)
        - Logs warning if token is not found or already revoked
        - Includes basic security audit logging
    """
    async with get_sql_session() as session:
        # Execute the update
        result = await session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == refresh_jti)
            .values(revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        await session.commit()

        # Log appropriate message based on result
        if result.rowcount == 0:
            logger.info(f"Refresh token not found or already revoked: {refresh_jti}")
        else:
            logger.info(f"Refresh token revoked: {refresh_jti}")


async def revoke_access_token_from_request(request: Request) -> None:
    """
    Extracts and revokes an access token from the Authorization header.

    Args:
        request: Incoming FastAPI request object

    Returns:
        None

    Note:
        Silently handles missing/invalid tokens and logs errors
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.debug("No access token in Authorization header")
        return

    token = auth_header.split(" ")[1]

    try:
        header = get_unverified_header(token)
        kid = header.get("kid", False)
        key = get_signing_key_by_kid(kid)

        payload = validate_token(token, "access")
        if payload.get("typ") != "access":
            logger.warning("Provided token is not an access token")
            return

        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            logger.warning("Access token missing jti or exp claim")
            return

        # Skip revocation if token already expired
        ttl = exp - datetime.now(timezone.utc).timestamp()
        if ttl <= 0:
            logger.debug("Access token already expired")
            return

        await revoke_access_token(jti)

    except jwt.PyJWTError as e:
        logger.warning(f"Access token decode error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during token revocation: {str(e)}")


async def revoke_access_token(jti: str) -> None:
    """
    Revokes an access token and adds it to the revocation cache.

    Args:
        jti: Unique token identifier

    Returns:
        None

    Raises:
        SQLAlchemyError: If database operations fail
    """
    async with get_sql_session() as session:
        try:
            token = await session.scalar(
                select(AccessToken).where(AccessToken.jti == jti)
            )

            if not token:
                logger.info(f"Token {jti} not found in database")
                return

            if token.revoked:
                logger.info(f"Token {jti} already revoked")
                return

            # Update database record
            token.revoked = True
            token.revoked_at = datetime.now(timezone.utc)
            await session.commit()

            # Add to Redis revocation cache
            ttl = int((token.expires_at - datetime.now(timezone.utc)).total_seconds())
            if ttl > 0:
                redis_client = await get_redis_client()
                await redis_client.setex(
                    f"papi:access_token_revoked:{jti}",
                    ttl,
                    "1",  # Using string value for consistency
                )

            logger.info(f"Revoked access token: {jti}")

        except SQLAlchemyError as db_err:
            await session.rollback()
            logger.error(f"Database error revoking token: {db_err}")
            raise


async def revoke_access_token_by_device_id(device_id: str) -> None:
    async with get_sql_session() as session:
        token = await session.scalar(
            select(AccessToken)
            .where(AccessToken.device_id == device_id)
            .where(AccessToken.revoked.is_(False))
        )

        if not token:
            logger.info(f"No active access tokens for {device_id} found")
            return
        else:
            await revoke_access_token(token.jti)


async def is_access_token_revoked(jti: str) -> bool:
    """
    Checks if an access token is revoked or expired.

    Verification steps:
    1. Check Redis revocation cache
    2. Check database for revocation status
    3. Verify token expiration

    Args:
        jti: Unique token identifier

    Returns:
        True if token is invalid (revoked/expired/not found), False otherwise
    """
    # Check Redis cache first
    redis_client = await get_redis_client()
    if await redis_client.exists(f"papi:access_token_revoked:{jti}"):
        return True

    # Check database record
    async with get_sql_session() as session:
        token = await session.scalar(select(AccessToken).where(AccessToken.jti == jti))

        if not token:
            return True  # Treat non-existent tokens as revoked

        # Check if token is expired or revoked
        current_time = datetime.now(timezone.utc)
        return token.revoked or token.expires_at < current_time


async def cleanup_expired_tokens() -> None:
    """Deletes expired access and refresh tokens from the database."""
    now = datetime.now(timezone.utc)

    async with get_sql_session() as session:
        # Delete expired access tokens
        access_result = await session.execute(
            delete(AccessToken).where(
                or_(
                    AccessToken.expires_at < now,
                    AccessToken.revoked.is_(True),
                )
            )
        )

        # Delete expired refresh tokens
        refresh_result = await session.execute(
            delete(RefreshToken).where(
                or_(
                    RefreshToken.expires_at < now,
                    RefreshToken.revoked.is_(True),
                )
            )
        )

        await session.commit()

        logger.info(
            f"Token cleanup: Removed {access_result.rowcount} access tokens "
            f"and {refresh_result.rowcount} refresh tokens"
        )
