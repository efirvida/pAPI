from typing import List, Optional

from casbin import AsyncEnforcer
from loguru import logger
from sqlalchemy import and_, select

from papi.core.db import get_redis_client, get_sql_session
from user_auth_system.models.casbin import AuthRules
from user_auth_system.schemas.policy import PolicyCreate, PolicyInDB

POLICY_UPDATE_CHANNEL = "casbin:policy_updated"


async def start_redis_policy_listener(enforcer: AsyncEnforcer) -> None:
    """
    Starts a listener on a Redis Pub/Sub channel to detect policy updates.

    When a message is received on the corresponding channel, the policy is reloaded in the enforcer.

    Args:
        enforcer (AsyncEnforcer): Instance of the Casbin enforcer to be updated.
    """
    redis_client = await get_redis_client()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(POLICY_UPDATE_CHANNEL)

    logger.info("Subscribed to Redis channel for policy updates")

    async for message in pubsub.listen():
        if message["type"] == "message":
            logger.info("Policy update received from Redis")
            await enforcer.load_policy()
            logger.info("Policies reloaded")


async def add_policy(policy: PolicyCreate) -> bool:
    """
    Adds a policy to the database if it does not already exist and notifies via Redis.

    Args:
        policy (PolicyCreate): Object containing the fields of the policy to be added.

    Returns:
        bool: True if the policy was inserted, False if it already existed.
    """
    subject = policy.subject.strip()
    object_ = policy.object.strip()
    action = policy.action.strip().lower()
    condition = policy.condition.strip()
    effect = policy.effect.strip().lower()

    redis_client = await get_redis_client()

    async with get_sql_session() as session:
        query = select(AuthRules).where(
            and_(
                AuthRules.v0 == subject,
                AuthRules.v1 == object_,
                AuthRules.v2 == action,
                AuthRules.v3 == condition,
                AuthRules.v4 == effect,
            )
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            return False

        new_policy = AuthRules(
            ptype="p",
            v0=subject,
            v1=object_,
            v2=action,
            v3=condition,
            v4=effect,
            v5=None,
        )
        session.add(new_policy)
        await session.commit()

    await redis_client.publish(POLICY_UPDATE_CHANNEL, "policy_updated")
    return True


async def remove_policy(policy: PolicyCreate) -> bool:
    """
    Removes a specific policy from the database and notifies the update via Redis.

    Args:
        policy (PolicyCreate): Object containing the fields of the policy to be removed.

    Returns:
        bool: True if the policy was removed, False if it did not exist.
    """
    subject = policy.subject.strip()
    object_ = policy.object.strip()
    action = policy.action.strip().lower()
    condition = policy.condition.strip()
    effect = policy.effect.strip().lower()

    redis_client = await get_redis_client()

    async with get_sql_session() as session:
        query = select(AuthRules).where(
            and_(
                AuthRules.v0 == subject,
                AuthRules.v1 == object_,
                AuthRules.v2 == action,
                AuthRules.v3 == condition,
                AuthRules.v4 == effect,
            )
        )
        result = await session.execute(query)
        policy_obj = result.scalar_one_or_none()

        if not policy_obj:
            return False

        await session.delete(policy_obj)
        await session.commit()

    await redis_client.publish(POLICY_UPDATE_CHANNEL, "policy_updated")
    return True


async def remove_policy_by_id(policy_id: int) -> bool:
    """
    Removes a policy from the database using its ID.

    Args:
        policy_id (int): ID of the policy to be removed.

    Returns:
        bool: True if the policy was removed, False if it was not found.
    """
    redis_client = await get_redis_client()

    async with get_sql_session() as session:
        policy_obj = await session.get(AuthRules, policy_id)
        if not policy_obj:
            return False

        await session.delete(policy_obj)
        await session.commit()

    await redis_client.publish(POLICY_UPDATE_CHANNEL, "policy_updated")
    return True


async def get_policy(policy: PolicyCreate) -> Optional[PolicyInDB]:
    """
    Retrieves a specific policy from the database.

    Args:
        policy (PolicyCreate): Object containing the fields of the policy to be retrieved.

    Returns:
        Optional[PolicyInDB]: Policy object if it exists, None otherwise.
    """
    subject = policy.subject.strip()
    object_ = policy.object.strip()
    action = policy.action.strip().lower()
    condition = policy.condition.strip()
    effect = policy.effect.strip().lower()

    async with get_sql_session() as session:
        query = select(AuthRules).where(
            and_(
                AuthRules.v0 == subject,
                AuthRules.v1 == object_,
                AuthRules.v2 == action,
                AuthRules.v3 == condition,
                AuthRules.v4 == effect,
            )
        )
        result = await session.execute(query)
        policy_obj = result.scalar_one_or_none()

        if policy_obj:
            return PolicyInDB(
                id=policy_obj.id,
                ptype=policy_obj.ptype,
                subject=policy_obj.v0,
                object=policy_obj.v1,
                action=policy_obj.v2,
                condition=policy_obj.v3,
                effect=policy_obj.v4,
            )

        return None


async def list_policies(
    subject: Optional[str] = None,
    object_: Optional[str] = None,
    action: Optional[str] = None,
    condition: Optional[str] = None,
    effect: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[PolicyInDB]:
    """
    Lists policies from the database with optional filters and pagination.

    Args:
        subject (Optional[str]): Filter by 'subject' field if provided.
        object_ (Optional[str]): Filter by 'object' field if provided.
        action (Optional[str]): Filter by 'action' field if provided.
        condition (Optional[str]): Filter by 'condition' field if provided.
        effect (Optional[str]): Filter by 'effect' field if provided.
        skip (int): Number of results to skip (for pagination).
        limit (int): Maximum number of results to return.

    Returns:
        List[PolicyInDB]: List of policies matching the filters.
    """
    filters = [AuthRules.ptype == "p"]

    if subject:
        filters.append(AuthRules.v0 == subject.strip())
    if object_:
        filters.append(AuthRules.v1 == object_.strip())
    if action:
        filters.append(AuthRules.v2 == action.strip().lower())
    if condition:
        filters.append(AuthRules.v3 == condition.strip())
    if effect:
        filters.append(AuthRules.v4 == effect.strip().lower())

    async with get_sql_session() as session:
        query = (
            select(AuthRules)
            .where(and_(*filters))
            .order_by(AuthRules.id)
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(query)
        policies = result.scalars().all()

    return [
        PolicyInDB(
            id=policy.id,
            ptype=policy.ptype,
            subject=policy.v0,
            object=policy.v1,
            action=policy.v2,
            condition=policy.v3,
            effect=policy.v4,
        )
        for policy in policies
    ]
