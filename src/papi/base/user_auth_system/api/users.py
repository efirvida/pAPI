from typing import Annotated, Optional

from fastapi import Body, Depends, Query, status
from sqlalchemy.exc import IntegrityError

from papi.core.exceptions import APIException
from papi.core.models.response import APIResponse, create_response
from papi.core.router import RESTRouter
from user_auth_system.config import auth_settings
from user_auth_system.crud.users import (
    create_user,
    delete_user,
    get_all_users,
    get_user_by_username,
    update_user,
)
from user_auth_system.schemas import (
    UserAdminUpdate,
    UserCreate,
    UserInDB,
    UserPublic,
    UserRead,
    UserSelfUpdate,
    UsersListResponse,
)
from user_auth_system.security.dependencies import (
    get_current_active_user,
    permission_required,
)
from user_auth_system.security.enums import PolicyAction
from user_auth_system.security.password import hash_password

router = RESTRouter(prefix="/user", tags=["Users Management & Access Control"])


@router.get(
    "/",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.READ)],
)
async def list_users(
    skip: int = Query(0, description="Pagination offset"),
    limit: int = Query(100, description="Items per page", le=200),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    username: Optional[str] = Query(
        None, description="Filter by username (partial match)"
    ),
    email: Optional[str] = Query(None, description="Filter by email (partial match)"),
    role: Optional[str] = Query(None, description="Filter by role name"),
    group: Optional[str] = Query(None, description="Filter by group name"),
):
    """
    List and filter users in the system with comprehensive filtering options.

    This endpoint provides paginated access to the user database with multiple filtering options.
    Results are sorted and can be filtered by various user attributes.
    Includes user status, role assignments, and group memberships.

    Permissions Required:
        - PolicyAction.READ permission
        - Administrative access

    Args:
        skip (int): Number of records to skip for pagination (default: 0)
        limit (int): Maximum number of records to return (default: 100, max: 200)
        is_active (bool, optional): Filter by user active status
        username (str, optional): Filter by partial username match
        email (str, optional): Filter by partial email match
        role (str, optional): Filter by exact role name
        group (str, optional): Filter by exact group name

    Returns:
        APIResponse: Response object containing:
            - data: UsersListResponse object with:
                - users: List of UserPublic objects
                - total: Total number of users matching filters
                - page: Current page number
                - per_page: Items per page
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_403_FORBIDDEN: If user lacks required permissions
            - HTTP_400_BAD_REQUEST: If invalid filter parameters are provided

    Security:
        - Requires authentication
        - Role-based access control
        - Pagination to prevent data dumps
        - Data filtering and sanitization
    """
    users = await get_all_users(
        skip=skip,
        limit=limit,
        is_active=is_active,
        username=username,
        email=email,
        role_name=role,
        group_name=group,
    )

    page = (skip // limit) if limit else 0

    data = UsersListResponse(
        users=[format_user_public(user) for user in users["users"]],
        total=users.get("total", 0),
        page=page,
        per_page=limit,
    )
    return create_response(
        data=data, success=True, message="Users retrieved successfully."
    )


@router.post("/", response_model=APIResponse)
async def create_new_user(user_data: UserCreate):
    """
    Create a new user account in the system.

    This endpoint handles new user registration with automatic password hashing,
    role assignment, and validation. Can be disabled system-wide through settings.

    The endpoint performs multiple validations:
    - Username/email uniqueness
    - Password strength requirements
    - Required field validation
    - Role and group assignment permissions

    Args:
        user_data (UserCreate): User creation data containing:
            - username: Unique username (required)
            - email: Valid email address (required)
            - password: Strong password meeting requirements (required)
            - full_name: User's full name (optional)
            - is_active: Account status (default: True)
            - roles: List of role names to assign (optional)
            - groups: List of group names to assign (optional)

    Returns:
        APIResponse: Response object containing:
            - data: Created UserPublic object with:
                - id: Generated user ID
                - username: User's username
                - email: User's email
                - full_name: User's full name
                - is_active: Account status
                - roles: Assigned roles
                - groups: Assigned groups
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_400_BAD_REQUEST: If registration is disabled
            - HTTP_409_CONFLICT: If username/email already exists
            - HTTP_422_UNPROCESSABLE_ENTITY: If validation fails

    Security:
        - Password hashing
        - Input validation
        - Duplicate prevention
        - Role validation
        - Activity logging
    """
    if not auth_settings.allow_registration:
        raise APIException(
            message="User registration is currently disabled.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
        )

    try:
        created_user = await create_user(user_data)
        return create_response(
            data=format_user_public(created_user),
            message="User created successfully.",
        )
    except IntegrityError:
        raise APIException(
            message="Username or email already exists.",
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
        )
    except ValueError as e:
        raise APIException(
            message=str(e.args[0]) if e.args else "Server error.",
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            code="PRECONDITION_FAILED",
        )
    except Exception:
        raise APIException(
            message="Failed to create user due to server error.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
        )


@router.get(
    "/me",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.READ)],
)
async def get_current_user_info(
    current_user: Annotated[UserRead, Depends(get_current_active_user)],
):
    """
    Retrieve the current authenticated user's public profile and information.

    This endpoint allows users to access their own profile information, including
    roles, groups, and permissions. Sensitive data like password hashes are excluded.

    Permissions Required:
        - PolicyAction.READ permission
        - Valid authentication token

    Returns:
        APIResponse: Response object containing:
            - data: UserPublic object with:
                - username: User's username
                - email: User's email address
                - full_name: User's full name
                - is_active: Account status
                - roles: List of assigned roles
                - groups: List of group memberships
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_401_UNAUTHORIZED: If not authenticated
            - HTTP_403_FORBIDDEN: If insufficient permissions
            - HTTP_404_NOT_FOUND: If user account not found

    Security:
        - Requires valid JWT token
        - Role-based access control
        - Data sanitization
    """
    return create_response(
        data=format_user_public(current_user), message="User retrieved successfully."
    )


@router.patch(
    "/me",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.PATCH)],
)
async def update_current_user_info(
    current_user: Annotated[UserRead, Depends(get_current_active_user)],
    update_data: UserSelfUpdate = Body(...),
):
    """
    Update the current authenticated user's profile information.

    This endpoint allows users to modify their own profile data including email,
    password, and personal information. Certain fields like roles and permissions
    cannot be modified through this endpoint.

    Permissions Required:
        - PolicyAction.PATCH permission
        - Valid authentication token

    Args:
        current_user (UserRead): Current authenticated user (from token)
        update_data (UserSelfUpdate): Update data containing:
            - email: New email address (optional)
            - password: New password (optional)
            - full_name: New full name (optional)
            - avatar: New avatar URL (optional)

    Returns:
        APIResponse: Response object containing:
            - data: Updated UserPublic object
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_400_BAD_REQUEST: If no update data provided
            - HTTP_404_NOT_FOUND: If user not found
            - HTTP_409_CONFLICT: If email already in use
            - HTTP_500_INTERNAL_SERVER_ERROR: For server errors

    Security:
        - Password hashing for password updates
        - Input validation
        - Field-level access control
        - Update logging
        - Conflict prevention
    """
    data = update_data.model_dump(exclude_unset=True)

    if not data:
        raise APIException(
            message="No update data provided.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="NO_DATA",
        )

    if "password" in data:
        data["hashed_password"] = hash_password(data.pop("password"))

    try:
        updated_user = await update_user(current_user.username, data)
        if not updated_user:
            raise APIException(
                message="User not found.",
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOT_FOUND",
            )

        return create_response(
            data=format_user_public(updated_user), message="User updated successfully."
        )

    except IntegrityError:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            code="INTEGRITY_ERROR",
            message="Email or username already in use.",
        )
    except Exception:
        raise APIException(
            code="UNEXPECTED_ERROR",
            message="Failed to update user due to server error.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.delete(
    "/me",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.DELETE)],
)
async def remove_current_user(
    current_user: Annotated[UserRead, Depends(get_current_active_user)],
):
    """
    Delete the currently authenticated user's account.

    This endpoint allows users to remove their own account from the system.
    The operation is irreversible and removes all user data, roles, and group memberships.
    Superusers/admins are prevented from deleting their own accounts for security.

    Permissions Required:
        - PolicyAction.DELETE permission
        - Valid authentication token

    Args:
        current_user (UserRead): Current authenticated user (from token)

    Returns:
        APIResponse: Response object containing:
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_403_FORBIDDEN: If user is a superuser
            - HTTP_404_NOT_FOUND: If user not found
            - HTTP_401_UNAUTHORIZED: If not authenticated
            - HTTP_500_INTERNAL_SERVER_ERROR: For server errors

    Security:
        - Requires authentication
        - Superuser protection
        - Cascade deletion handling
        - Activity logging
        - Session invalidation
    """
    if current_user.is_superuser:
        raise APIException(
            message="Admins cannot delete their own account.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    success = await delete_user(current_user.username)
    if not success:
        raise APIException(
            message="User not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return create_response(message="User account deleted successfully.")


@router.get(
    "/{username}",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.READ)],
)
async def read_user_by_username(username: str):
    """
    Retrieve a user's public profile by their username.

    This endpoint allows querying user information by username. It returns the public
    profile information while protecting sensitive data. Useful for user lookups
    and profile viewing.

    Permissions Required:
        - PolicyAction.READ permission
        - Valid authentication token

    Args:
        username (str): The username of the user to retrieve

    Returns:
        APIResponse: Response object containing:
            - data: UserPublic object with:
                - username: User's username
                - email: User's email (if visible)
                - full_name: User's full name
                - is_active: Account status
                - roles: List of assigned roles
                - groups: List of group memberships
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_404_NOT_FOUND: If user not found
            - HTTP_403_FORBIDDEN: If insufficient permissions
            - HTTP_401_UNAUTHORIZED: If not authenticated

    Security:
        - Data visibility control
        - Permission checking
        - Input validation
        - Activity logging
        - Rate limiting
    """
    user = await get_user_by_username(username)
    if not user:
        raise APIException(
            message="User not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return create_response(
        data=format_user_public(user), message="User retrieved successfully."
    )


@router.patch(
    "/{username}",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.PATCH)],
)
async def update_user_by_username(
    username: str,
    update_data: UserAdminUpdate = Body(...),
):
    """
    Update an existing user's profile by an administrator.

    This endpoint allows administrators to modify user profiles, including sensitive
    fields like activation status and role assignments. Special protections are in
    place for superuser accounts.

    Permissions Required:
        - PolicyAction.PATCH permission
        - Administrative privileges
        - Valid authentication token

    Args:
        username (str): Username of the user to update
        update_data (UserAdminUpdate): Update data containing:
            - email: New email address (optional)
            - password: New password (optional)
            - full_name: New full name (optional)
            - is_active: Account status (optional)
            - is_superuser: Superuser status (optional, restricted)
            - roles: New role assignments (optional)
            - groups: New group assignments (optional)

    Returns:
        APIResponse: Response object containing:
            - data: Updated UserPublic object
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_404_NOT_FOUND: If user not found
            - HTTP_400_BAD_REQUEST: If no update data provided
            - HTTP_409_CONFLICT: If email/username conflict
            - HTTP_403_FORBIDDEN: If trying to modify protected fields
            - HTTP_500_INTERNAL_SERVER_ERROR: For server errors

    Security:
        - Role-based access control
        - Superuser protection
        - Password hashing
        - Field-level permissions
        - Activity logging
        - Input validation
    """
    target_user = await get_user_by_username(username)
    if not target_user:
        raise APIException(
            message="User not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    update_fields = update_data.model_dump(exclude_unset=True)
    if not update_fields:
        raise APIException(
            message="No update data provided.",
            code="NO_DATA",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if "password" in update_fields:
        password = update_fields.pop("password")
        update_fields["hashed_password"] = hash_password(password)

    if not target_user.is_superuser:
        for field in {"is_active", "is_superuser"}:
            update_fields.pop(field, None)

    try:
        updated_user = await update_user(username, update_fields)
        if not updated_user:
            raise APIException(
                code="NOT_FOUND",
                message="User not found during update.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return create_response(
            data=format_user_public(updated_user), message="User updated successfully."
        )

    except IntegrityError:
        raise APIException(
            code="INTEGRITY_ERROR",
            message="Email or username already in use.",
            status_code=status.HTTP_409_CONFLICT,
        )
    except Exception:
        raise APIException(
            code="UNEXPECTED_ERROR",
            message="Failed to update user due to server error.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.delete(
    "/{username}",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.DELETE)],
)
async def remove_user_by_username(
    username: str,
    current_user: Annotated[UserRead, Depends(get_current_active_user)],
):
    """
    Delete a user account by username.
    """
    if current_user.is_superuser and current_user.username == username:
        raise APIException(
            code="FORBIDDEN",
            message="Admins cannot delete their own account.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    success = await delete_user(username)
    if not success:
        raise APIException(
            code="NOT_FOUND",
            message="User not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return create_response(message="User account deleted successfully.")


# Utility functions


def format_user_public(user: UserRead | UserInDB) -> UserPublic:
    """
    Convert a UserRead instance to a public-facing UserPublic object.
    """
    user_data = user.model_dump(exclude={"hashed_password", "groups", "roles"})
    return UserPublic(
        **user_data,
        roles=[role.name for role in user.roles],
        groups=[attr.name for attr in user.groups],
    )
