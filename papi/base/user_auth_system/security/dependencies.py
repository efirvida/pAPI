from typing import Annotated, List, Optional

import jwt
from casbin import AsyncEnforcer
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from pydantic import TypeAdapter

from user_auth_system import config
from user_auth_system.crud.users import get_user_by_username
from user_auth_system.schemas import UserInDB

from .audit import log_security_event_async
from .cache_utils import cache_user, get_cached_user
from .enforcer import (
    CasbinRequest,
    build_temp_enforcer,
    debug_enforcement,
    get_enforcer,
)
from .enums import AuditLogKeys, PolicyAction
from .jwt_utils import decode_jwt, try_historical_keys
from .rate_limit import check_auth_rate_limit

PREFIX = "/auth"
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{PREFIX}/token",
    scheme_name="JWT",
    auto_error=False,  # Let the dependency handle the error
)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    """
    Retrieves and authenticates the current user from a JWT token.
    If the token is valid, fetches user information from cache or DB.

    Args:
        token (str): JWT token provided in the Authorization header.

    Returns:
        UserInDB: Authenticated user model.

    Raises:
        HTTPException: For missing or invalid token, or if user not found.
    """
    if not token:
        # Don't expose specific authentication errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Add brute force protection
        await check_auth_rate_limit(token)

        payload = await decode_jwt(token)

        # Verify token expiration explicitly
        if "exp" not in payload:
            raise jwt.InvalidTokenError("Token has no expiration")

    except jwt.ExpiredSignatureError:
        # Don't try historical keys for expired tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidSignatureError:
        # Log potential tampering attempts
        logger.warning("Invalid token signature detected")
        payload = await try_historical_keys(token)
    except jwt.PyJWTError:
        # Don't expose internal JWT errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    username = payload.get("sub")
    if not username:
        logger.error("Token missing subject claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    # Try to get from cache first
    user = None
    try:
        cached = await get_cached_user(username)
        if cached:
            user = TypeAdapter(UserInDB).validate_json(cached)
    except Exception:
        # Skip logging cache errors to reduce overhead
        pass

    # If not in cache, fetch from DB
    if not user:
        user = await get_user_by_username(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )

        # Only try to cache if fetched from DB
        try:
            await cache_user(username, user.model_dump_json())
        except Exception:
            # Continue without logging cache failures
            pass

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
