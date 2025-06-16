from typing import Annotated, List, Optional

import jwt
from casbin import AsyncEnforcer
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from pydantic import TypeAdapter

from user_auth_system.config import config
from user_auth_system.crud.users import get_user_by_username
from user_auth_system.schemas import UserInDB
from user_auth_system.security.tokens import is_access_token_revoked

from .audit import log_security_event_async
from .cache_utils import (
    cache_user,
    get_cached_user,
)
from .enforcer import (
    CasbinRequest,
    build_temp_enforcer,
    debug_enforcement,
    get_enforcer,
)
from .enums import AuditLogKeys, PolicyAction
from .jwt_utils import validate_token
from .rate_limit import check_auth_rate_limit

PREFIX = "/auth"
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{PREFIX}/login",
    scheme_name="JWT",
    auto_error=False,  # Let the dependency handle the error
)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    """
    Retrieves and authenticates the current user from a JWT token.
    Implements multiple security layers including token validation,
    revocation checking, and rate limiting.

    Security Features:
    - Token presence validation
    - Rate limiting for authentication attempts
    - JWT signature verification
    - Expiration validation
    - Token revocation (blacklist) check
    - Historical key rotation support
    - Cache-first user lookup
    - Secure error handling

    Args:
        token (str): JWT token provided in the Authorization header.

    Returns:
        UserInDB: Authenticated user model.

    Raises:
        HTTPException: For any authentication failure
    """
    # Validate token presence
    if not token:
        logger.warning("Authentication attempt without token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Brute force protection - rate limit token verification attempts
        await check_auth_rate_limit(token)

        # Decode and verify token with current key
        payload = validate_token(token, "access")

        # Validate critical claims
        jti = payload.get("jti")
        if not jti:
            logger.error(f"Token missing jti claim: {token[:20]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        if "exp" not in payload:
            logger.error(f"Token missing expiration claim: {token[:20]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # Check token revocation status
        if await is_access_token_revoked(jti):
            logger.info(f"Token revocado detectado: {jti}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )

    except jwt.ExpiredSignatureError:
        # Special handling for expired tokens (don't try historical keys)
        logger.info(f"Expired token attempt: {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    except jwt.PyJWTError as e:
        # Generic JWT error handling
        logger.warning(f"JWT validation error: {str(e)} - Token: {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    except HTTPException:
        # Re-raise our own exceptions
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error",
        )

    # Validate subject claim
    username = payload.get("sub")
    if not username:
        logger.error(f"Token missing subject claim: {token[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    # User retrieval - cache-first strategy
    user = None
    try:
        # Try to get user from cache
        cached_data = await get_cached_user(username)
        if cached_data:
            user = TypeAdapter(UserInDB).validate_json(cached_data)
            logger.debug(f"User {username} retrieved from cache")
    except Exception as e:
        logger.warning(f"Cache read error for {username}: {str(e)}")

    # Fallback to database if not in cache
    if not user:
        try:
            user = await get_user_by_username(username)
            if not user:
                logger.warning(f"User not found in DB: {username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )

            # Cache user for future requests
            try:
                await cache_user(username, user.model_dump_json())
                logger.debug(f"Cached user data for {username}")
            except Exception as e:
                logger.warning(f"Cache write error for {username}: {str(e)}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Database error for {username}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )

    # # Additional security check: validate token issue time against user's last password change
    # if security.validate_token_against_password_change:
    #     token_iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
    #     if user.password_changed_at and token_iat < user.password_changed_at:
    #         logger.info(f"Token issued before password change for {username}")
    #         raise HTTPException(
    #             status_code=status.HTTP_401_UNAUTHORIZED,
    #             detail="Token invalidated by password change",
    #         )

    return user


async def get_current_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
) -> UserInDB:
    """
    Verifies that the authenticated user is active.

    Args:
        current_user (UserInDB): Authenticated user instance.

    Returns:
        UserInDB: Active user model.

    Raises:
        HTTPException: If the user's account is inactive.
    """
    if not current_user.is_active:
        logger.warning(f"Access attempt by inactive user: {current_user.username}")
        await log_security_event_async(
            AuditLogKeys.ACCESS_ATTEMPT_INACTIVE, {"username": current_user.username}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )
    return current_user


def normalize_path(path: str) -> str:
    """Normalizes the URL path for consistent policy evaluation.

    This function ensures that all paths are in a consistent format:
    - Removes trailing slashes except for root path
    - Ensures path starts with a slash
    - Collapses multiple slashes into single ones
    - Preserves query parameters and fragments

    Args:
        path (str): The URL path to normalize

    Returns:
        str: Normalized path string

    Examples:
        >>> normalize_path("/users/")  # returns '/users'
        >>> normalize_path("users")  # returns '/users'
        >>> normalize_path("/")  # returns '/'
        >>> normalize_path("//users///test/")  # returns '/users/test'
    """
    if not path:
        return "/"

    # Ensure path starts with slash and normalize multiple slashes
    normalized = "/" + "/".join(filter(None, path.split("/")))

    # Handle root path specially
    if normalized == "/":
        return normalized

    # Remove trailing slash for non-root paths
    return normalized.rstrip("/")


def permission_required(
    action: PolicyAction,
    resource: Optional[str] = None,
    required_roles: Optional[List[str]] = None,
    required_groups: Optional[List[str]] = None,
):
    """
    Factory function to create permission validation dependencies using RBAC/ABAC.

    This function creates a FastAPI dependency that combines role-based and
    attribute-based access control. It performs the following checks in order:
    1. Verifies user authentication and active status
    2. Validates required roles if specified
    3. Validates required groups if specified
    4. Evaluates Casbin policies for fine-grained permissions

    Args:
        action (PolicyAction): The action being performed (e.g., READ, WRITE).
            Must be a valid PolicyAction enum value.
        resource (str, optional): Resource path to validate against.
            If not provided, uses the current request path.
            Example: "/users" or "/groups/{id}"
        required_roles (List[str], optional): List of role names that can access.
            The user must have at least one of these roles.
            Example: ["admin", "moderator"]
        required_groups (List[str], optional): List of group names that can access.
            The user must belong to at least one of these groups.
            Example: ["staff", "support"]

    Returns:
        Depends: FastAPI dependency that performs the permission checks.
            When injected, raises HTTPException if access is denied.

    Raises:
        HTTPException:
            - 401: If user is not authenticated
            - 403: If user lacks required permissions
            - 404: If resource doesn't exist

    Example:
        @router.get(
            "/users",
            dependencies=[permission_required(
                action=PolicyAction.READ,
                required_roles=["admin"],
                required_groups=["staff"]
            )]
        )
        async def list_users():
            ...
    """

    async def dependency(
        request: Request,
        user: UserInDB = Depends(get_current_active_user),
        enforcer: AsyncEnforcer = Depends(get_enforcer),
    ):
        resource_path = normalize_path(resource or str(request.url.path))

        if required_roles and not any(r.name in required_roles for r in user.roles):
            logger.warning(
                f"User '{user.username}' missing required roles: {required_roles}"
            )
            raise HTTPException(status_code=403, detail="Insufficient role permissions")

        if required_groups and not any(g.name in required_groups for g in user.groups):
            logger.warning(
                f"User '{user.username}' missing required groups: {required_groups}"
            )
            raise HTTPException(
                status_code=403, detail="Insufficient group permissions"
            )

        user_attrs = {
            "id": str(user.id),
            "username": user.username,
            "roles": [r.name for r in user.roles],
            "groups": [g.name for g in user.groups],
            "is_active": user.is_active,
        }

        auth_request = CasbinRequest(user_attrs, resource_path, action.value)
        temp_enforcer = await build_temp_enforcer(enforcer, auth_request, user)

        if config.logger.level == "DEBUG":
            allowed = await debug_enforcement(temp_enforcer, auth_request)
        else:
            allowed = temp_enforcer.enforce(
                auth_request.sub, auth_request.obj, auth_request.act
            )

        await log_permission_result(
            allowed=allowed,
            username=user.username,
            resource=resource_path,
            action=action,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )

    return Depends(dependency)


async def log_permission_result(
    *, allowed: bool, username: str, resource: str, action: PolicyAction
) -> None:
    """
    Logs the result of a permission check for audit purposes.

    Args:
        allowed (bool): Whether the permission was granted
        username (str): The username requesting access
        resource (str): The resource being accessed
        action (PolicyAction): The attempted action
    """
    event = {
        "username": username,
        "resource": resource,
        "action": action,
        "policy": "allowed" if allowed else "denied",
    }

    # Only log denied events to reduce I/O
    if not allowed:
        await log_security_event_async(AuditLogKeys.PERMISSION_DENIED, event)
        # Log at warning level only for denied permissions
        logger.warning(
            f"Permission denied: user={username} resource={resource} action={action}"
        )
