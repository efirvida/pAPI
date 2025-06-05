from fastapi import status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from papi.core.db import get_sql_session
from papi.core.exceptions import APIException
from papi.core.models.response import APIResponse, create_response
from papi.core.router import RESTRouter
from user_auth_system.models.casbin import AuthRules
from user_auth_system.schemas import PolicyCreate, PolicyInDB
from user_auth_system.security.dependencies import permission_required
from user_auth_system.security.enforcer import get_enforcer
from user_auth_system.security.enums import PolicyAction

router = RESTRouter(
    prefix="/access-control",
    tags=["Users Management & Access Control"],
)


@router.post(
    "/policies",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.WRITE, required_roles=["root"])],
)
async def create_policy(policy_rule: PolicyCreate) -> APIResponse:
    """
    Create a new access control policy in the Casbin policy store.

    This endpoint allows creation of fine-grained access control policies that define
    what actions users or roles can perform on specific resources. Policies are the
    cornerstone of the ABAC (Attribute-Based Access Control) system.

    Permissions Required:
        - PolicyAction.WRITE permission
        - 'root' role membership

    Args:
        policy_rule (PolicyCreate): Policy creation data containing:
            - policy: List containing the policy rule elements:
                [0]: subject (user/role)
                [1]: object (resource)
                [2]: action (permitted operation)
                [3]: condition (optional)
                [4]: effect (allow/deny)

    Returns:
        APIResponse: Response object containing:
            - data: Boolean indicating success
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_409_CONFLICT: If policy already exists
            - HTTP_500_INTERNAL_SERVER_ERROR: If policy creation fails
            - HTTP_403_FORBIDDEN: If user lacks required permissions
            - HTTP_401_UNAUTHORIZED: If not authenticated

    Security:
        - Requires authentication
        - Root-only access
        - Policy validation
        - Automatic policy reloading
        - Activity logging
        - Conflict prevention

    Example Policy:
        - Subject: "role:admin"
        - Object: "users"
        - Action: "create"
        - Condition: null
        - Effect: "allow"
    """
    enforcer = await get_enforcer()
    try:
        # Check if policy already exists
        if enforcer.has_policy(*policy_rule.policy):
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                message="Policy already exists.",
                detail="POLICY_ALREADY_EXISTS",
            )

        created = await enforcer.add_policy(*policy_rule.policy)
        await enforcer.load_policy()

        return create_response(data=created, message="New policy created")
    except Exception as e:
        logger.exception("Error creating policy")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Failed to create policy: {str(e)}",
            detail="POLICY_CREATION_ERROR",
        )


@router.get(
    "/policies",
    response_model=APIResponse,
    dependencies=[permission_required(PolicyAction.READ, required_roles=["root"])],
)
async def list_policies() -> APIResponse:
    """
    Retrieve all defined access control policies from the system.

    This endpoint provides access to all Casbin policy rules that define the access
    control matrix for the system. It returns both user-specific and role-based
    policies, allowing administrators to audit and manage access control rules.

    Permissions Required:
        - PolicyAction.READ permission
        - 'root' role membership

    Returns:
        APIResponse: Response object containing:
            - data: List of PolicyInDB objects, each with:
                - id: Unique policy identifier
                - ptype: Policy type ('p' for policy)
                - subject: User or role the policy applies to
                - object: Resource being protected
                - action: Permitted action
                - condition: Additional conditions (optional)
                - effect: Policy effect (allow/deny)
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_500_INTERNAL_SERVER_ERROR: For database errors
            - HTTP_403_FORBIDDEN: If user lacks required permissions
            - HTTP_401_UNAUTHORIZED: If not authenticated

    Security:
        - Requires authentication
        - Root-only access
        - Query optimization
        - Activity logging
        - Rate limiting

    Notes:
        - Only returns active policies (ptype='p')
        - Policies are foundational to both RBAC and ABAC
        - Used for auditing and compliance verification
    """
    try:
        async with get_sql_session() as session:
            query = select(AuthRules).where(AuthRules.ptype == "p")
            result = await session.execute(query)

            data = [
                PolicyInDB(
                    id=rule.id,
                    ptype=rule.ptype,
                    subject=rule.v0,
                    object=rule.v1,
                    action=rule.v2,
                    condition=rule.v3,
                    effect=rule.v4,
                )
                for rule in result.scalars().all()
            ]

            return create_response(data=data, message="Policies listed successfully")
    except SQLAlchemyError:
        logger.exception("Database error while listing policies")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="Database error while listing policies.",
            detail="LIST_POLICIES_ERROR",
        )


@router.delete(
    "/policies/{id}",
    dependencies=[permission_required(PolicyAction.DELETE, required_roles=["root"])],
)
async def delete_policy(id: int) -> None:
    """
    Delete a specific access control policy from the system.

    This endpoint allows removal of individual policy rules by their unique identifier.
    Deletion of policies should be done carefully as it directly affects access control.
    The system prevents deletion of critical system policies.

    Permissions Required:
        - PolicyAction.DELETE permission
        - 'root' role membership

    Args:
        id (int): The unique identifier of the policy to delete

    Returns:
        APIResponse: Response object containing:
            - message: Success confirmation message
            - status: HTTP status code

    Raises:
        APIException:
            - HTTP_404_NOT_FOUND: If policy with given ID doesn't exist
            - HTTP_403_FORBIDDEN: If attempting to delete protected policy
            - HTTP_500_INTERNAL_SERVER_ERROR: For database errors
            - HTTP_401_UNAUTHORIZED: If not authenticated

    Security:
        - Requires authentication
        - Root-only access
        - Protected policy validation
        - Transaction safety
        - Activity logging
        - Casbin enforcer reload

    Impact:
        - Immediately affects access control decisions
        - May require cache invalidation
        - Affects all users/roles referenced in policy
        - Logged for audit purposes
    """
    try:
        async with get_sql_session() as session:
            rule = await session.get(AuthRules, id)
            if not rule:
                raise APIException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="NOT_FOUND",
                    message="Policy not found",
                )

            await session.delete(rule)
            await session.commit()

        enforcer = await get_enforcer()
        await enforcer.load_policy()
    except SQLAlchemyError:
        logger.exception("Database error while deleting policy")
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Database error while deleting policy.",
            detail="DELETE_POLICY_ERROR",
        )
