from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from papi.core.db import get_sql_session
from user_auth_system.models import Group
from user_auth_system.schemas import GroupBase, GroupCreate


async def get_groups() -> list[Group]:
    """
    Retrieve all groups from the database.

    Returns:
        list[Group]: A list of all group objects.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Group))
        return result.scalars().all()


async def create_group(group_in: GroupCreate) -> Group:
    """
    Create a new group in the database.

    Args:
        group_in (GroupCreate): Group data to be created.

    Returns:
        Group: The newly created group object.

    Raises:
        ValueError: If the group already exists or cannot be created.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Group).where(Group.name == group_in.name))
        existing_group = result.scalar_one_or_none()
        if existing_group:
            raise ValueError(f"Group '{group_in.name}' already exists.")

        group = Group(**group_in.model_dump())
        db.add(group)
        try:
            await db.commit()
            await db.refresh(group)
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Could not create group '{group_in.name}'.")

    return group


async def update_group(group_id: int, group_in: GroupBase) -> Optional[Group]:
    """
    Update an existing group by ID.

    Args:
        group_id (int): The ID of the group to update.
        group_in (GroupBase): The fields to update.

    Returns:
        Optional[Group]: The updated group object if found, otherwise None.

    Raises:
        ValueError: If the update operation fails.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Group).where(Group.id == group_id))
        group = result.scalar_one_or_none()

        if not group:
            return None

        for key, value in group_in.model_dump(exclude_unset=True).items():
            setattr(group, key, value)

        try:
            await db.commit()
            await db.refresh(group)
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Could not update group with ID {group_id}.")

    return group


async def delete_group(group_id: int) -> bool:
    """
    Delete a group by ID.

    Args:
        group_id (int): The ID of the group to delete.

    Returns:
        bool: True if the group was deleted, False if not found.

    Raises:
        ValueError: If the deletion operation fails.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Group).where(Group.id == group_id))
        group = result.scalar_one_or_none()

        if not group:
            return False

        await db.delete(group)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Could not delete group with ID {group_id}.")

    return True
