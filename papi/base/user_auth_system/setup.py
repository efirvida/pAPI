import os
import re
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from papi.core.addons import AddonSetupHook
from papi.core.db import get_sql_session
from user_auth_system.models import Role, User
from user_auth_system.schemas.policy import PolicyCreate
from user_auth_system.schemas.root import RootUserEnv
from user_auth_system.security.casbin_policies import (
    add_policy,
    start_redis_policy_listener,
)
from user_auth_system.security.enforcer import get_enforcer
from user_auth_system.security.enums import PolicyAction, PolicyEffect
from user_auth_system.security.password import hash_password, verify_password

# RFC 5322 compliant email validation regex (simplified version)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def is_valid_email(email: str) -> bool:
    """
    Validate email format using RFC 5322 compliant regex.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    return bool(EMAIL_REGEX.fullmatch(email))


async def init_root_policies(root_env: RootUserEnv) -> None:
    """
    Initialize default Casbin policies granting full access to:
    1. The root username directly
    2. Any user with the root role

    Args:
        root_env: Root environment configuration object

    Raises:
        RuntimeError: If policy initialization fails
        ValueError: For invalid policy configuration
    """
    try:
        # Policy for direct root user access
        root_user_policy = PolicyCreate(
            subject=root_env.username,
            object="/*",
            action=PolicyAction.ALL,
            condition="True",
            effect=PolicyEffect.ALLOW,
        )

        # Policy for root role access
        root_role_policy = PolicyCreate(
            subject=f"role:{root_env.role_name}",
            object="/*",
            action=PolicyAction.ALL,
            condition="True",
            effect=PolicyEffect.ALLOW,
        )

        await add_policy(root_user_policy)
        await add_policy(root_role_policy)
        logger.info("Root access policies initialized successfully")

    except ValueError as ve:
        logger.error(f"Policy configuration error: {ve}")
        raise
    except Exception as e:
        logger.exception("Unexpected error during policy initialization")
        raise RuntimeError("Root policy initialization failed") from e


class AuthSystemInitializer(AddonSetupHook):
    """
    System initialization hook for authentication subsystem. Handles:
    - Root user creation
    - Root role creation
    - Casbin policy initialization
    - Security warnings for production environments

    Supports both empty-system initialization and environment-based configuration.
    """

    async def _create_root_role(
        self, root_env: RootUserEnv, session: AsyncSession
    ) -> Role:
        """
        Ensure the root role exists in the database (idempotent operation).

        Args:
            root_env: Root environment configuration
            session: Async database session

        Returns:
            Existing or newly created Role instance

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            root_role = await session.scalar(
                select(Role).where(Role.name == root_env.role_name).limit(1)
            )

            if not root_role:
                root_role = Role(
                    name=root_env.role_name,
                    description="Superadmin role with full system access",
                )
                session.add(root_role)
                await session.commit()
                logger.info(f"Created root role: {root_env.role_name}")
            else:
                logger.debug(f"Root role already exists: {root_env.role_name}")

            return root_role

        except SQLAlchemyError as e:
            logger.exception("Failed to create root role")
            await session.rollback()
            raise RuntimeError("Database error during role creation") from e

    async def _create_root_user(
        self, session: AsyncSession, root_env: RootUserEnv, role: Role
    ) -> None:
        """
        Create root user with hashed credentials and superuser privileges.

        Args:
            session: Async database session
            root_env: Root environment configuration
            role: Root role instance

        Raises:
            RuntimeError: If user creation fails
            ValueError: For invalid email format
        """
        # Validate email format before creation
        if not is_valid_email(root_env.email):
            raise ValueError(f"Invalid root email format: {root_env.email}")

        try:
            root_user = User(
                username=root_env.username,
                full_name="Root Administrator",
                email=root_env.email,
                hashed_password=hash_password(root_env.password),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                roles=[role],
                is_active=True,
                is_superuser=True,
            )
            session.add(root_user)
            await session.commit()
            logger.info(f"Root user created: {root_env.username}")

        except SQLAlchemyError as e:
            logger.exception("Failed to create root user")
            await session.rollback()
            raise RuntimeError("Database error during user creation") from e

    async def _warn_env_exposure(self, root_env: RootUserEnv) -> None:
        """
        Generate security warnings about .env file exposure if:
        - .env file exists
        - Contains root credentials

        Args:
            root_env: Root environment configuration
        """
        if not os.path.exists(".env"):
            return

        warning_msg = (
            f"⚠️  SECURITY WARNING: Environment file '.env' contains active "
            f"credentials for root user '{root_env.username}'. "
            f"Remove root credentials from '.env' in production environments "
            f"to prevent unauthorized access. ⚠️"
        )
        logger.warning(warning_msg)

    async def run(self) -> None:
        """
        Main initialization workflow:
        1. Check for existing users (skip if system already initialized)
        2. Validate environment configuration
        3. Create root role and user
        4. Initialize access policies
        5. Start policy listener
        6. Generate security warnings

        Raises:
            RuntimeError: For any critical initialization failure
        """
        try:
            async with get_sql_session() as session:
                # Check if system already has users
                user_count = await session.scalar(select(func.count(User.id)))
                root_env = RootUserEnv()

                if user_count and user_count > 0:
                    logger.info(
                        "Users exist in DB, skipping root account system bootstrap."
                    )

                    result = await session.execute(
                        select(User).where(User.username == root_env.username)
                    )
                    existing_root_user = result.scalars().first()

                    if existing_root_user and verify_password(
                        root_env.password, existing_root_user.hashed_password
                    ):
                        await self._warn_env_exposure(root_env)
                    return

                # New system initialization
                logger.info("Initializing root authentication system")

                # Process security warnings from environment config
                for warning in root_env.get_security_warnings():
                    logger.warning(warning)

                # Create root role and user
                root_role = await self._create_root_role(root_env, session)
                await self._create_root_user(session, root_env, root_role)

                # Initialize access policies
                await init_root_policies(root_env)

                # Start policy synchronization listener
                casbin_enforcer = await get_enforcer()
                await start_redis_policy_listener(casbin_enforcer)

                logger.success("Authentication system initialized successfully")
                await self._warn_env_exposure(root_env)

        except SQLAlchemyError as e:
            logger.exception("Database error during initialization")
            raise RuntimeError("Database operation failed") from e
        except Exception as e:
            logger.exception("Critical initialization error")
            raise RuntimeError("System initialization aborted") from e
