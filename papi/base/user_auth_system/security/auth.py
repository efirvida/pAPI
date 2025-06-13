from datetime import datetime, timezone
from typing import Optional

import bcrypt
from fastapi import BackgroundTasks, HTTPException, Request, status
from loguru import logger

from user_auth_system.schemas import UserInDB

from .audit import log_security_event_sync
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
    background_tasks: Optional[BackgroundTasks] = None,
) -> Optional[UserInDB]:
    """
    Authenticates a user with brute-force protection and background logging.

    Args:
        username: Username to authenticate
        password: Password to verify
        request: Current request object
        background_tasks: FastAPI background task handler

    Returns:
        Authenticated user object or None
    """
    # Rejection: system-wide lockout
    if await is_system_locked_out():
        logger.warning("Authentication attempt during system lockout")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="System temporarily locked due to excessive attempts",
        )

    logger.info(f"Authentication attempt for user: {username}")
    user = await get_user_by_username(username)
    ip_address = request.client.host if request.client else "unknown"
    event_details = {"username": username, "ip": ip_address}

    # Rejection: per-user lockout
    if await has_excessive_failed_attempts(username):
        if background_tasks:
            background_tasks.add_task(
                log_security_event_sync, AuditLogKeys.LOGIN_LOCKOUT, event_details
            )
        logger.warning(f"Account temporarily locked: {username}")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to excessive attempts",
        )

    # Timing defense
    start_time = datetime.now(timezone.utc)
    valid_credentials = False

    if user:
        if verify_password(password, user.hashed_password):
            if user.is_active:
                valid_credentials = True
                await reset_failed_attempts(ip_address, username)
                if background_tasks:
                    background_tasks.add_task(
                        log_security_event_sync,
                        AuditLogKeys.LOGIN_SUCCESS,
                        event_details,
                    )
            else:
                if background_tasks:
                    background_tasks.add_task(
                        log_security_event_sync,
                        AuditLogKeys.LOGIN_INACTIVE,
                        event_details,
                    )
        else:
            # Fall-through to simulate delay
            bcrypt.checkpw(
                b"dummy_password",
                b"$2b$12$012345678901234567890uDYoY8eDvtvY7vjWzozOAzFvwP9m",
            )
    else:
        # Simulate password check if user does not exist
        bcrypt.checkpw(
            b"dummy_password",
            b"$2b$12$012345678901234567890uDYoY8eDvtvY7vjWzozOAzFvwP9m",
        )

    if not valid_credentials:
        await record_failed_attempt(ip_address, username)
        if background_tasks:
            background_tasks.add_task(
                log_security_event_sync, AuditLogKeys.LOGIN_FAILED, event_details
            )

    if logger.level("DEBUG").no >= logger.level("DEBUG").no:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.debug(f"Authentication completed in {duration:.4f}s")

    return user if valid_credentials else None
