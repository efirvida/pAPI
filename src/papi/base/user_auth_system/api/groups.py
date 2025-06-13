from fastapi import Path, status
from sqlalchemy.exc import IntegrityError

from papi.core.exceptions import APIException
from papi.core.models.response import APIResponse, create_response
from papi.core.router import RESTRouter
from user_auth_system.crud.groups import (
    create_group,
    delete_group,
    get_groups,
    update_group,
)
from user_auth_system.schemas import Group, GroupBase, GroupCreate
from user_auth_system.security.dependencies import permission_required
from user_auth_system.security.enums import PolicyAction

router = RESTRouter(prefix="/groups", tags=["Users Management & Access Control"])


@router.get(
    "/",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.READ, required_roles=["root"])],
)
async def list_groups() -> APIResponse:
    """
    Retrieve a list of all user groups in the system.
    
    This endpoint provides a comprehensive list of all user groups with their basic information.
    Access to this endpoint requires root privileges or specific read permissions.
    Groups are essential for role-based access control and permission management.

    Permissions Required:
        - PolicyAction.READ permission
        - 'root' role membership

    Returns:
        APIResponse: Response object containing:
            - data: List of Group objects with:
                - id: Unique group identifier
                - name: Group name
                - description: Group description
            - message: Success confirmation message
            - status: HTTP status code

    Security:
        - Requires authentication
        - Role-based access control
        - Activity is logged for audit purposes
    """
    groups = await get_groups()
    data = [
        Group(
            name=g.name,
            id=g.id,
            description=g.description,
        )
        for g in groups
        if g is not None
    ]
    return create_response(data=data, message="All groups retrieved successfully.")


@router.post(
    "/",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.WRITE, required_roles=["root"])],
)
async def create_new_group(group: GroupCreate) -> APIResponse:
    """
    Create a new user group in the system.
    
    This endpoint allows creation of new groups for organizing users and managing permissions.
    Groups are fundamental components of the RBAC system and can be assigned specific permissions.

    Permissions Required:
        - PolicyAction.WRITE permission
        - 'root' role membership

    Args:
        group (GroupCreate): Group creation data with:
            - name: Unique group name (required)
            - description: Group description (optional)

    Returns:
        APIResponse: Response object containing:
            - data: Created Group object with:
                - id: Generated group ID
                - name: Group name
                - description: Group description
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_409_CONFLICT: If group name already exists
            - HTTP_500_INTERNAL_SERVER_ERROR: For database integrity errors

    Security:
        - Requires authentication
        - Role-based access control
        - Input validation
        - Activity logging
    """
    try:
        new_group = await create_group(group)
        return create_response(
            data=Group(
                name=new_group.name,
                id=new_group.id,
                description=new_group.description,
            ),
            message=f"New group '{group.name}' created successfully.",
        )
    except ValueError:
        raise APIException(
            code="ALREADY_EXISTS",
            message=f"Group '{group.name}' already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )
    except IntegrityError:
        raise APIException(
            code="INTEGRITY_ERROR",
            message="Database integrity error while creating group.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.patch(
    "/{group_id}",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.PATCH, required_roles=["root"])],
)
async def update_existing_group(
    group_id: int = Path(..., title="Group ID", ge=1),
    group_in: GroupBase = ...,
) -> APIResponse:
    """
    Update an existing group's information by its ID.
    
    This endpoint allows modification of group details while maintaining group relationships
    and permissions. The update operation is atomic and validates all constraints.

    Permissions Required:
        - PolicyAction.PATCH permission
        - 'root' role membership

    Args:
        group_id (int): Unique identifier of the group to update (Path parameter)
        group_in (GroupBase): Updated group data with:
            - name: New group name (optional)
            - description: New group description (optional)

    Returns:
        APIResponse: Response object containing:
            - data: Updated Group object with:
                - id: Group ID
                - name: Updated name
                - description: Updated description
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_404_NOT_FOUND: If group with given ID doesn't exist
            - HTTP_409_CONFLICT: If new name conflicts with existing group

    Security:
        - Requires authentication
        - Role-based access control
        - Input validation
        - Activity logging
    """
    updated = await update_group(group_id, group_in)
    if not updated:
        raise APIException(
            code="NOT_FOUND",
            message=f"Group with ID '{group_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return create_response(
        data=Group(
            name=updated.name,
            id=updated.id,
            description=updated.description,
        ),
        message=f"Group '{updated.name}' updated successfully.",
    )


@router.delete(
    "/{group_id}",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.DELETE, required_roles=["root"])],
)
async def delete_existing_group(
    group_id: int = Path(..., title="Group ID", ge=1),
) -> APIResponse:
    """
    Delete an existing group from the system.
    
    This endpoint permanently removes a group and all its associations.
    The operation will fail if the group doesn't exist or if it's a protected system group.
    Group deletion will automatically remove all group memberships but won't affect users.

    Permissions Required:
        - PolicyAction.DELETE permission
        - 'root' role membership

    Args:
        group_id (int): Unique identifier of the group to delete (Path parameter, must be >= 1)

    Returns:
        APIResponse: Response object containing:
            - message: Success confirmation message
            - status: HTTP status code
            - data: None

    Raises:
        APIException:
            - HTTP_404_NOT_FOUND: If group with given ID doesn't exist
            - HTTP_400_BAD_REQUEST: If attempting to delete a protected system group
            - HTTP_409_CONFLICT: If group has active dependencies

    Security:
        - Requires authentication
        - Role-based access control
        - Deletion validation
        - Activity logging for audit trail
    """
    success = await delete_group(group_id)
    if not success:
        raise APIException(
            code="NOT_FOUND",
            message=f"Group with ID '{group_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return create_response(message="Group deleted successfully.")
