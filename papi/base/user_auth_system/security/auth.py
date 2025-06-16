from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import BackgroundTasks, HTTPException, Request, status
from loguru import logger

from user_auth_system.schemas import UserInDB

from .audit import log_security_event_async
from .dependencies import get_user_by_username
from .enums import AuditLogKeys
from .lockout import (
    has_excessive_failed_attempts,
    is_system_locked_out,
    record_failed_attempt,
    reset_failed_attempts,
)
from .password import verify_password


async def authenticate_user(
    username: str,
    password: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Optional[UserInDB]:
    """
    Authenticates a user with comprehensive security measures:
    - System-wide lockout protection
    - Per-user account lockout
    - Timing attack prevention
    - Security event auditing
    - Credential validation

    Args:
        username: User identifier
        password: Plaintext password
        request: HTTP request object
        background_tasks: For security logging

    Returns:
        Authenticated user object if successful, None otherwise

    Raises:
        HTTPException: 423 for locked accounts/system, 401 for invalid credentials
    """
    # System-wide lockout check
    if await is_system_locked_out():
        logger.warning("Authentication attempt during system-wide lockout")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="System temporarily locked due to excessive attempts",
        )

    # Prepare security event details
    ip_address = request.client.host if request.client else "unknown"
    event_details = {
        "username": username,
        "ip": ip_address,
        "user_agent": request.headers.get("User-Agent", "unknown")[:100],
    }

    # Per-user lockout check
    if await has_excessive_failed_attempts(username):
        await log_security_event_async(AuditLogKeys.LOGIN_LOCKOUT, event_details)
        logger.warning(f"Account locked for '{username}' from {ip_address}")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to excessive attempts",
        )

    # Start timing for consistent response time
    start_time = datetime.now(timezone.utc)
    valid_credentials = False
    user = None

    try:
        # Retrieve user (if exists)
        user = await get_user_by_username(username)

        # Validate credentials
        if user:
            if verify_password(password, user.hashed_password):
                if user.is_active:
                    valid_credentials = True
                    await reset_failed_attempts(ip_address, username)
                    background_tasks.add_task(
                        log_security_event_async,
                        AuditLogKeys.LOGIN_SUCCESS,
                        event_details,
                    )
                    logger.info(f"Successful login for '{username}' from {ip_address}")
                else:
                    background_tasks.add_task(
                        log_security_event_async,
                        AuditLogKeys.LOGIN_INACTIVE,
                        event_details,
                    )
                    logger.warning(f"Login attempt for inactive account: '{username}'")
            else:
                # Simulate password check timing for non-existent users
                bcrypt.checkpw(
                    b"dummy_password",
                    b"$2b$12$012345678901234567890uDYoY8eDvtvY7vjWzozOAzFvwP9m",
                )
                logger.info(f"Invalid password for '{username}' from {ip_address}")
        else:
            # Simulate password check timing for non-existent users
            bcrypt.checkpw(
                b"dummy_password",
                b"$2b$12$012345678901234567890uDYoY8eDvtvY7vjWzozOAzFvwP9m",
            )
            logger.info(f"Login attempt for unknown user: '{username}'")

        # Record failed attempt if credentials invalid
        if not valid_credentials:
            await record_failed_attempt(ip_address, username)
            background_tasks.add_task(
                log_security_event_async, AuditLogKeys.LOGIN_FAILED, event_details
            )

    except Exception as e:
        logger.error(f"Authentication error for '{username}': {str(e)}")
        # Fail securely without revealing details
        bcrypt.checkpw(
            b"dummy_password",
            b"$2b$12$012345678901234567890uDYoY8eDvtvY7vjWzozOAzFvwP9m",
        )
        await record_failed_attempt(ip_address, username)
        return None

    finally:
        # Ensure consistent timing regardless of outcome
        elapsed = datetime.now(timezone.utc) - start_time
        min_duration = timedelta(milliseconds=500)
        if elapsed < min_duration:
            remaining = min_duration - elapsed
            await asyncio.sleep(remaining.total_seconds())

    return user if valid_credentials else None
