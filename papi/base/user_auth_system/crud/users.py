from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from papi.core.db import get_sql_session
from user_auth_system.config import auth_settings
from user_auth_system.crud.roles import create_role
from user_auth_system.models import Group, Role, User
from user_auth_system.schemas import (
    PolicyCreate,
    RoleCreate,
    RoleRead,
    UserCreate,
    UserInDB,
)
from user_auth_system.security.casbin_policies import add_policy
from user_auth_system.security.enums import PolicyAction, PolicyEffect
from user_auth_system.security.password import hash_password


async def get_user_by_username(username: str) -> Optional[UserInDB]:
    """
    Retrieve a user and their relationships from the database by username.

    Args:
        username (str): Username to search for.

    Returns:
        Optional[UserInDB]: A validated user object, or None if not found.
    """
    try:
        async with get_sql_session() as session:
            stmt = (
                select(User)
                .where(User.username == username)
                .options(
                    selectinload(User.roles),
                    selectinload(User.groups),
                )
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user is None:
                logger.trace(f"User not found: {username}")
                return None

            return UserInDB.model_validate(user)
    except SQLAlchemyError:
        logger.exception("SQLAlchemy error while fetching user.")
        raise
    except Exception:
        logger.exception("Unexpected error while fetching user.")
        raise


async def create_user(user: UserCreate) -> UserInDB:
    """
    Creates a new user in the database with proper role assignment and security measures.

    Args:
        user_data: Dictionary containing validated user data with keys:
            - username: Unique user identifier
            - email: Valid email address
            - password: Plaintext password (will be hashed)
            - full_name: Optional full name
            - is_active: Account status flag (default True)
            - is_superuser: Admin privileges flag (default False)

    Returns:
        UserInDB: Created user object with populated fields

    Raises:
        ValueError: For invalid input data

    Steps:
        1. Hash password
        2. Create user in database
        3. Create roles if needed
        4. Assign default roles to the new user
        5. Create ABAC policies for the new user
        6. Return complete user object
    """

    async with get_sql_session() as session:
        try:
            existing_user = await session.execute(
                select(User).where(
                    (User.username == user.username) | (User.email == user.email)
                )
            )
            result = existing_user.scalar_one_or_none()
            if result:
                if result.username == user.username:
                    detail = f"Username {user.username} already exists"
                else:
                    detail = f"Email {user.email} already registered"
                logger.warning(f"User creation aborted: {detail}")
                raise ValueError(detail)

            user_data = user.model_dump(exclude_unset=True)

            # Hash password before storage
            if "password" in user_data:
                user_data["hashed_password"] = hash_password(user_data.pop("password"))
            else:
                raise ValueError("Password is required for new users")

            # Create user object
            new_user = User(**user_data)
            session.add(new_user)
            await session.commit()

            result = await session.execute(
                select(User)
                .options(selectinload(User.roles))
                .where(User.id == new_user.id)
            )
            new_user = result.scalar_one()
            logger.info(f"User created: {new_user.username}")

            # Create roles and assign
            assigned_roles = []
            for role_name in auth_settings.default_user_roles:
                role_schema = RoleCreate(name=role_name, description="")
                role = await create_role(role_schema)
                if role not in new_user.roles:
                    new_user.roles.append(role)
                    assigned_roles.append(role)

                base_usre_policy = PolicyCreate(
                    subject=f"role:{role.name}",
                    object="/user/me",
                    action=PolicyAction.ALL,
                    condition=f"'{role.name}' in r.sub['roles']",
                    effect=PolicyEffect.ALLOW,
                )

                await add_policy(base_usre_policy)

            await session.commit()
            logger.info(
                f"Assigned roles to {new_user.username}: {[r.name for r in assigned_roles]}"
            )
            roles = [
                RoleRead(id=role.id, name=role.name, description=role.description)
                for role in new_user.roles
            ]
            return UserInDB(
                id=new_user.id,
                username=new_user.username,
                email=new_user.email,
                full_name=new_user.full_name,
                hashed_password=new_user.hashed_password,
                is_active=new_user.is_active,
                is_superuser=new_user.is_superuser,
                roles=roles,
                groups=[],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            await session.rollback()
            logger.exception(f"User creation failed: {str(e)}")
            raise ValueError(e)


async def update_user(username: str, update_data: dict) -> Optional[UserInDB]:
    """
    Update an existing user.

    Args:
        username: Username to update
        update_data: Data to update

    Returns:
        Updated UserInDB object or None if not found
    """
    async with get_sql_session() as session:
        try:
            result = await session.execute(
                select(User)
                .options(selectinload(User.roles), selectinload(User.groups))
                .where(User.username == username)
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            for key, value in update_data.items():
                setattr(user, key, value)
            user.updated_at = datetime.now()

            await session.commit()
            await session.refresh(user)
            return UserInDB.model_validate(user, from_attributes=True)
        except Exception as e:
            await session.rollback()
            logger.error(f"User update failed: {str(e)}")
            raise


async def delete_user(username: str) -> bool:
    """
    Delete a user from the database.

    Args:
        username: Username to delete

    Returns:
        True if deleted successfully, False if user not found
    """
    async with get_sql_session() as session:
        try:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one_or_none()

            if not user:
                return False

            await session.delete(user)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f"User deletion failed: {str(e)}")
            raise


async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    role_name: Optional[str] = None,
    group_name: Optional[str] = None,
) -> Dict[str, Union[int, List[UserInDB]]]:
    """
    Retrieve paginated and filtered list of users from the database.

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        is_active: Filter by active status
        username: Filter by username (partial match)
        email: Filter by email (partial match)
        role_name: Filter by role name
        group_name: Filter by attribute name

    Returns:
        Dictionary with:
          - users: List of UserInDB objects
          - total: Total number of users matching the filters
    """
    async with get_sql_session() as session:
        # Base query with relationships
        base_query = select(User).options(
            selectinload(User.roles), selectinload(User.groups)
        )

        # Apply filters
        if is_active is not None:
            base_query = base_query.where(User.is_active == is_active)

        if username:
            base_query = base_query.where(User.username.ilike(f"%{username}%"))

        if email:
            base_query = base_query.where(User.email.ilike(f"%{email}%"))

        if role_name:
            base_query = base_query.join(User.roles).where(Role.name == role_name)

        if group_name:
            base_query = base_query.join(User.groups).where(Group.name == group_name)

        # Get total count of matching records
        count_query = select(func.count()).select_from(base_query.subquery())
        total_count = (await session.execute(count_query)).scalar()

        # Apply pagination and execute
        paginated_query = base_query.offset(skip).limit(limit)
        result = await session.execute(paginated_query)
        users = result.scalars().all()

        return {
            "users": [UserInDB.model_validate(user) for user in users],
            "total": total_count,
        }
