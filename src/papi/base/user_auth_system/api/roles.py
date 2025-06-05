from fastapi import status
from sqlalchemy.exc import IntegrityError

from papi.core.exceptions import APIException
from papi.core.models.response import APIResponse, create_response
from papi.core.router import RESTRouter
from user_auth_system.crud.roles import (
    create_role,
    delete_role,
    get_roles,
    update_role,
)
from user_auth_system.schemas import Role, RoleBase, RoleCreate
from user_auth_system.security.dependencies import permission_required
from user_auth_system.security.enums import PolicyAction

router = RESTRouter(
    prefix="/roles",
    tags=["Users Management & Access Control"],
)


@router.get(
    "/",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.READ, required_roles=["root"])],
)
async def list_roles() -> APIResponse:
    """
    Retrieve a list of all roles in the system.

    This endpoint provides access to all defined roles in the system. Roles are fundamental
    components of the RBAC system and define sets of permissions that can be assigned to users.
    Only root users can access this endpoint to maintain security.

    Permissions Required:
        - PolicyAction.READ permission
        - 'root' role membership

    Returns:
        APIResponse: Response object containing:
            - data: List of Role objects, each with:
                - id: Unique role identifier
                - name: Role name
                - description: Role description
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_403_FORBIDDEN: If user lacks root privileges
            - HTTP_401_UNAUTHORIZED: If not authenticated

    Security:
        - Requires authentication
        - Root-only access
        - Activity logging
        - Role hierarchy validation
    """
    roles = await get_roles()
    data = [
        Role(
            name=g.name,
            id=g.id,
            description=g.description,
        )
        for g in roles
        if g is not None
    ]
    return create_response(data=data, message="All roles retrieved successfully.")


@router.post(
    "/",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.WRITE, required_roles=["root"])],
)
async def create_new_role(role: RoleCreate) -> APIResponse:
    """
    Create a new role in the system.

    This endpoint allows creation of new roles for permission management. Roles are used
    to group permissions and can be assigned to users. Only root users can create roles
    to maintain security integrity.

    Permissions Required:
        - PolicyAction.WRITE permission
        - 'root' role membership

    Args:
        role (RoleCreate): Role creation data containing:
            - name: Unique role name (required)
            - description: Role description (optional)
            - permissions: List of permission strings (optional)

    Returns:
        APIResponse: Response object containing:
            - data: Created Role object with:
                - id: Generated role ID
                - name: Role name
                - description: Role description
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_409_CONFLICT: If role name already exists
            - HTTP_500_INTERNAL_SERVER_ERROR: For database integrity errors
            - HTTP_403_FORBIDDEN: If user lacks root privileges
            - HTTP_401_UNAUTHORIZED: If not authenticated

    Security:
        - Requires authentication
        - Root-only access
        - Name uniqueness validation
        - Permission validation
        - Activity logging
    """
    try:
        new_role = await create_role(role)
        return create_response(
            data=Role(
                name=new_role.name,
                id=new_role.id,
                description=new_role.description,
            ),
            message=f"New role '{new_role.name}' created successfully.",
        )
    except ValueError:
        raise APIException(
            code="ALREADY_EXISTS",
            message=f"Role '{role.name}' already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )
    except IntegrityError:
        raise APIException(
            code="INTEGRITY_ERROR",
            message="Database integrity error while creating role.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        raise APIException(
            code="UNEXPECTED_ERROR",
            message=f"Unexpected error: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.patch(
    "/{role_id}",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.PATCH, required_roles=["root"])],
)
async def edit_role(role_id: int, role_data: RoleBase) -> APIResponse:
    """
    Update an existing role's information.

    This endpoint allows modification of role details and permissions. Only root users
    can modify roles to ensure system security. Some system-defined roles may have
    additional protection against modifications.

    Permissions Required:
        - PolicyAction.PATCH permission
        - 'root' role membership

    Args:
        role_id (int): The unique identifier of the role to update
        role_data (RoleBase): Update data containing:
            - name: New role name (optional)
            - description: New role description (optional)
            - permissions: Updated permission list (optional)

    Returns:
        APIResponse: Response object containing:
            - data: Updated Role object with:
                - id: Role ID
                - name: Updated role name
                - description: Updated description
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_404_NOT_FOUND: If role with given ID doesn't exist
            - HTTP_409_CONFLICT: If new role name conflicts
            - HTTP_403_FORBIDDEN: If attempting to modify protected role
            - HTTP_401_UNAUTHORIZED: If not authenticated
            - HTTP_400_BAD_REQUEST: If no update data provided

    Security:
        - Requires authentication
        - Root-only access
        - Protected role validation
        - Permission integrity checks
        - Activity logging
        - Change tracking
    """
    updated = await update_role(role_id, role_data)
    if not updated:
        raise APIException(
            code="NOT_FOUND",
            message=f"Role with ID '{role_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return create_response(
        data=Role(
            name=updated.name,
            id=updated.id,
            description=updated.description,
        ),
        message=f"Role '{updated.name}' updated successfully.",
    )


@router.delete(
    "/{role_id}",
    dependencies=[permission_required(PolicyAction.DELETE, required_roles=["root"])],
)
async def delete_existing_role(role_id: int):
    """
    Delete a role by ID.

    Raises:
        - APIException: If role does not exist.
    """
    success = await delete_role(role_id)
    if not success:
        raise APIException(
            code="NOT_FOUND",
            message=f"Role with ID '{role_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return create_response(message="Role deleted successfully.")
