from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request, status
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger

from papi.core.exceptions import APIException
from papi.core.router import RESTRouter
from user_auth_system.schemas import Token
from user_auth_system.security import security
from user_auth_system.security.auth import authenticate_user
from user_auth_system.security.dependencies import PREFIX
from user_auth_system.security.tokens import create_access_token

router = RESTRouter(prefix=PREFIX, tags=["Authentication"])


@router.post(
    "/token",
    response_model=Token,
    summary="Obtain access token",
)
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    background_tasks: BackgroundTasks,
) -> Token:
    """
    Authenticate a user and return a JWT access token if credentials are valid.

    This endpoint handles user authentication and implements security measures including:
    - Brute force protection with IP-based rate limiting
    - Account lockout after multiple failed attempts
    - Background audit logging of all authentication attempts
    - Secure token generation with configurable expiration

    Args:
        request (Request): The current HTTP request containing client information like IP address
        form_data (OAuth2PasswordRequestForm): OAuth2 form containing:
            - username: User's unique identifier
            - password: User's password (will be verified against hashed storage)
        background_tasks (BackgroundTasks): FastAPI background tasks handler for audit logging

    Returns:
        Token: JWT access token object containing:
            - access_token: The JWT token string
            - token_type: Type of token (always "bearer")
            - expires_in: Token expiration timestamp in UTC

    Raises:
        APIException:
            - HTTP_423_LOCKED: If the system is temporarily locked due to excessive attempts
            - HTTP_401_UNAUTHORIZED: If credentials are invalid
        HTTPException: For other authentication-related errors
    """
    client_ip = request.client.host

    try:
        user = await authenticate_user(
            form_data.username, form_data.password, request, background_tasks
        )
    except HTTPException as exc:
        logger.warning(
            f"[AUTH] Account lockout triggered from IP {client_ip} for user '{form_data.username}'"
        )
        raise APIException(
            status_code=status.HTTP_423_LOCKED,
            message="System temporarily locked due to excessive attempts.",
            code="SYSTEM_LOCKED",
        ) from exc

    if not user:
        logger.info(
            f"[AUTH] Failed login from IP {client_ip} for user '{form_data.username}'"
        )
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Incorrect username or password.",
            code="UNAUTHORIZED",
        )

    logger.info(
        f"[AUTH] Successful login for user '{user.username}' from IP {client_ip}"
    )

    token_expiration = timedelta(minutes=security.access_token_expire_minutes)
    expiration_time = datetime.now(timezone.utc) + token_expiration

    access_token = await create_access_token(
        data={"sub": user.username}, expires_delta=token_expiration
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expiration_time,
    )
