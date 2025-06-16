from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy import select, update

from papi.core.db import get_sql_session
from papi.core.exceptions import APIException
from papi.core.models.response import APIResponse
from papi.core.response import create_response
from papi.core.router import RESTRouter
from user_auth_system.config import security
from user_auth_system.models.token import AccessToken, RefreshToken
from user_auth_system.schemas import LoginRequest, Token, UserRead
from user_auth_system.security.auth import authenticate_user
from user_auth_system.security.dependencies import PREFIX, get_current_active_user
from user_auth_system.security.tokens import (
    create_access_token,
    create_or_replace_refresh_token,
    revoke_access_token_from_request,
    revoke_refresh_token,
    validate_token,
)

router = RESTRouter(prefix=PREFIX, tags=["Authentication"])


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate user and obtain tokens",
    status_code=status.HTTP_200_OK,
)
async def login_for_access_token(
    login_request: LoginRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Token:
    """
    Authenticates user credentials and issues JWT tokens.

    Security features:
    - Brute-force protection
    - Device-based authentication
    - Secure token issuance with rotation
    - Audit logging

    Args:
        login_request: User credentials and device info
        request: HTTP request object
        background_tasks: For security background processing

    Returns:
        Token response with access and refresh tokens

    Raises:
        APIException: For authentication failures or locked accounts
    """
    client_ip = request.client.host if request.client else "unknown"
    username = login_request.username.strip()
    masked_username = f"{username[:3]}***"  # For secure logging

    try:
        # Authenticate user with brute-force protection
        user = await authenticate_user(
            username, login_request.password, request, background_tasks
        )
    except HTTPException as exc:
        logger.warning(f"Account lockout for IP {client_ip} user '{masked_username}'")
        raise APIException(
            status_code=status.HTTP_423_LOCKED,
            message="System temporarily locked due to excessive attempts",
            code="account_locked",
        ) from exc

    if not user:
        logger.info(f"Failed login from {client_ip} for user '{masked_username}'")
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Incorrect username or password",
            code="authentication_failed",
        )

    logger.info(f"Successful login: '{user.username}' from {client_ip}")

    # Validate device ID presence
    device_id = (login_request.device_id or "").strip()
    if not device_id:
        logger.warning(f"Missing device ID for user '{user.username}'")
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Device ID is required",
            code="missing_device_id",
        )

    # Prepare token metadata
    user_agent = request.headers.get("User-Agent", "unknown")[:500]

    # Issue tokens
    access_token = await create_access_token(
        data={"sub": user.username, "device_id": device_id}
    )
    refresh_token, _, _ = await create_or_replace_refresh_token(
        subject=user.username,
        device_id=device_id,
        user_agent=user_agent,
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    status_code=status.HTTP_200_OK,
)
async def refresh_token_endpoint(
    refresh_token: Annotated[str, Body(..., embed=True)],
) -> Token:
    """
    Issues new access and refresh tokens using a valid refresh token.

    Security process:
    1. Validates refresh token
    2. Checks token status in database
    3. Revokes old refresh token
    4. Issues new token pair

    Args:
        refresh_token: Valid refresh token string

    Returns:
        New token pair with expiration information

    Raises:
        APIException: 401 for invalid tokens
        APIException: 500 for internal errors
    """
    try:
        # Validate token structure and signature
        payload = validate_token(refresh_token, expected_type="refresh")
        jti = payload["jti"]
        subject = payload["sub"]
        device_id = payload["device_id"]

        async with get_sql_session() as session:
            # Verify token status in database
            db_token = await session.scalar(
                select(RefreshToken).where(RefreshToken.jti == jti)
            )

            if not db_token:
                logger.warning(f"Refresh token not found: {jti}")
                raise APIException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="UNAUTHORIZED",
                    message="Invalid refresh token",
                )

            if db_token.revoked:
                logger.info(f"Attempted use of revoked token: {jti}")
                raise APIException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="UNAUTHORIZED",
                    message="Token has been revoked",
                )

            if db_token.expires_at < datetime.now(timezone.utc):
                logger.info(f"Expired token presented: {jti}")
                raise APIException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="UNAUTHORIZED",
                    message="Token expired",
                )

            # Token rotation: revoke old, issue new
            await revoke_refresh_token(jti)
            new_refresh_token, _, _ = await create_or_replace_refresh_token(
                subject, db_token.device_id, db_token.user_agent
            )

            # Create new access token
            access_token = await create_access_token(
                data={"sub": subject, "device_id": device_id}
            )

            # Calculate expiration time for response
            access_exp = datetime.now(timezone.utc) + timedelta(
                minutes=security.access_token_expire_minutes
            )

        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=access_exp,
        )

    except HTTPException:
        # Re-raise handled authentication errors
        raise
    except Exception as e:
        logger.exception(f"Token refresh failed: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Token refresh failed",
            code="token_refresh_error",
        )


@router.post(
    "/logout",
    summary="Logout from current device",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
)
async def logout_current_device(
    request: Request,
    refresh_token: Annotated[str, Body(embed=True)],
) -> APIResponse:
    """
    Revokes both access and refresh tokens for the current device session.

    Security process:
    1. Validates refresh token
    2. Revokes access token from request header
    3. Revokes presented refresh token

    Args:
        request: HTTP request containing access token
        refresh_token: Refresh token to revoke

    Returns:
        Success confirmation

    Raises:
        APIException: For invalid tokens or revocation failures
    """
    try:
        # Validate refresh token
        payload = validate_token(refresh_token, expected_type="refresh")

        # Revoke both tokens
        await revoke_access_token_from_request(request)
        await revoke_refresh_token(payload["jti"])

        logger.info(f"Successful logout for device {payload['device_id']}")
        return create_response(message="Logged out successfully")

    except HTTPException as he:
        logger.warning(f"Logout warning: {he.detail}")
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Logout failed",
            code="logout_failed",
            detail=he.detail,
        )
    except Exception as e:
        logger.exception(f"Logout error: {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Logout failed",
        )


@router.post(
    "/logout-all",
    summary="Logout from all devices",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
)
async def logout_all_devices(
    current_user: Annotated[UserRead, Depends(get_current_active_user)],
) -> APIResponse:
    """
    Revokes all active tokens for the authenticated user across all devices.

    Use cases:
    - Account compromise recovery
    - Full account logout
    - Security policy enforcement

    Args:
        current_user: Authenticated user from dependency

    Returns:
        Success confirmation with revocation counts

    Raises:
        APIException: For revocation failures
    """
    username = current_user.username
    try:
        async with get_sql_session() as session:
            # Revoke all refresh tokens
            refresh_result = await session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.subject == username,
                    RefreshToken.revoked.is_(False),
                )
                .values(revoked=True, revoked_at=datetime.now(timezone.utc))
            )
            refresh_count = refresh_result.rowcount

            # Revoke all access tokens
            access_result = await session.execute(
                update(AccessToken)
                .where(
                    AccessToken.subject == username,
                    AccessToken.revoked.is_(False),
                )
                .values(revoked=True, revoked_at=datetime.now(timezone.utc))
            )
            access_count = access_result.rowcount

            await session.commit()

        logger.info(
            f"Logged out all devices: "
            f"{refresh_count} refresh tokens and "
            f"{access_count} access tokens revoked for '{username}'"
        )

        return create_response(
            message=f"Logged out of all devices. {refresh_count + access_count} tokens revoked"
        )

    except Exception as e:
        logger.exception(f"Logout-all failed for '{username}': {str(e)}")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="logout_error",
            message="Full logout failed",
        )
