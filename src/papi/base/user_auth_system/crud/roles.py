from typing import Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from papi.core.db import get_sql_session
from user_auth_system.models import Role
from user_auth_system.schemas import RoleBase, RoleCreate


async def get_roles() -> list[Role]:
    """
    Retrieve all roles from the database.

    Returns:
        list[Role]: A list of all role objects.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Role))
        return result.scalars().all()


async def create_role(role_in: RoleCreate) -> Role:
    """
    Creates a new role in the database if it does not already exist.

    Args:
        role_in (RoleCreate): The input data containing the name and attributes of the role to be created.

    Returns:
        Role: The newly created role object, or the existing one if it already exists.

    Raises:
        ValueError: If the role could not be created due to a database integrity error.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Role).where(Role.name == role_in.name))
        existing_role = result.scalar_one_or_none()
        if existing_role:
            logger.warning(f"Role '{role_in.name}' already exists.")
            return existing_role

        role = Role(**role_in.model_dump())
        db.add(role)
        try:
            await db.commit()
            await db.refresh(role)
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Could not create role '{role_in.name}'.")

    return role


async def update_role(role_id: int, role_in: RoleBase) -> Optional[Role]:
    """
    Update an existing role by ID.

    Args:
        role_id (int): The ID of the role to update.
        role_in (RoleBase): The fields to update.

    Returns:
        Optional[Role]: The updated role object if found, otherwise None.

    Raises:
        ValueError: If the update operation fails.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()

        if not role:
            return None

        for key, value in role_in.model_dump(exclude_unset=True).items():
            setattr(role, key, value)

        try:
            await db.commit()
            await db.refresh(role)
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Could not update role with ID {role_id}.")

    return role


async def delete_role(role_id: int) -> bool:
    """
    Delete a role by ID.

    Args:
        role_id (int): The ID of the role to delete.

    Returns:
        bool: True if the role was deleted, False if not found.

    Raises:
        ValueError: If the deletion operation fails.
    """
    async with get_sql_session() as db:
        result = await db.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()

        if not role:
            return False

        await db.delete(role)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Could not delete role with ID {role_id}.")

    return True
