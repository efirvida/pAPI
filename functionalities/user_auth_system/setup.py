import os
import re
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from papi.core.addons import AddonSetupHook
from papi.core.db import get_sql_session
from papi.core.settings import get_config
from user_auth_system.models import Role, User
from user_auth_system.schemas.policy import PolicyCreate
from user_auth_system.schemas.root import RootUserEnv
from user_auth_system.security.casbin_policies import (
    add_policy,
    start_redis_policy_listener,
)
from user_auth_system.security.enforcer import get_enforcer
from user_auth_system.security.enums import PolicyAction, PolicyEffect
from user_auth_system.security.key_manager import key_manager
from user_auth_system.security.password import hash_password
from user_auth_system.security.tokens import cleanup_expired_tokens

config = get_config()

# RFC 5322 compliant email validation regex
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$"
)


def is_valid_email(email: str) -> bool:
    """
    Validates email format against RFC 5322 specification.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    return bool(EMAIL_REGEX.fullmatch(email))


async def init_root_policies(root_env: RootUserEnv) -> None:
    """
    Initializes default access policies for root user and root role.

    Policies grant:
    - Full access to root username
    - Full access to root role members

    Args:
        root_env: Root environment configuration

    Raises:
        RuntimeError: If policy initialization fails
    """
    try:
        # Policy for direct root user access
        root_user_policy = PolicyCreate(
            subject=root_env.username,
            object="/*",
            action=PolicyAction.ALL,
            condition="True",
            effect=PolicyEffect.ALLOW,
            description="Root user full access policy",
        )

        # Policy for root role access
        root_role_policy = PolicyCreate(
            subject=f"role:{root_env.role_name}",
            object="/*",
            action=PolicyAction.ALL,
            condition="True",
            effect=PolicyEffect.ALLOW,
            description="Root role full access policy",
        )

        await add_policy(root_user_policy)
        await add_policy(root_role_policy)
        logger.info("Root access policies initialized successfully")

    except Exception as e:
        logger.critical(f"Policy initialization failed: {str(e)}")
        raise RuntimeError("Root policy initialization failed") from e


class AuthSystemInitializer(AddonSetupHook):
    """
    Authentication system initialization hook. Handles:
    - Root role creation
    - Root user creation
    - Access policy initialization
    - Security warnings for sensitive configurations

    Execution is idempotent and only runs on first system startup.
    """

    async def _create_root_role(
        self, root_env: RootUserEnv, session: AsyncSession
    ) -> Role:
        """
        Ensures the root role exists in the database (idempotent).

        Args:
            root_env: Root environment configuration
            session: Database session

        Returns:
            Existing or created root Role instance

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            # Check for existing role
            existing_role = await session.scalar(
                select(Role).where(Role.name == root_env.role_name)
            )

            if existing_role:
                logger.debug(f"Root role already exists: {root_env.role_name}")
                return existing_role

            # Create new role
            new_role = Role(
                name=root_env.role_name,
                description="System super-administrator role with full privileges",
                is_protected=True,  # Prevent accidental deletion
            )
            session.add(new_role)
            await session.commit()
            logger.info(f"Created root role: {root_env.role_name}")
            return new_role

        except SQLAlchemyError as e:
            logger.error("Root role creation failed")
            await session.rollback()
            raise RuntimeError("Database error during role creation") from e

    async def _create_root_user(
        self, session: AsyncSession, root_env: RootUserEnv, role: Role
    ) -> None:
        """
        Creates root user account with secure credentials.

        Args:
            session: Database session
            root_env: Root environment configuration
            role: Root role instance

        Raises:
            RuntimeError: If user creation fails
            ValueError: For invalid email format
        """
        # Validate email format
        if not is_valid_email(root_env.email):
            raise ValueError(f"Invalid root email format: {root_env.email}")

        try:
            # Check for existing user
            existing_user = await session.scalar(
                select(User).where(User.username == root_env.username)
            )
            if existing_user:
                logger.debug(f"Root user already exists: {root_env.username}")
                return

            # Create new root user
            new_user = User(
                username=root_env.username,
                full_name="System Administrator",
                email=root_env.email,
                hashed_password=hash_password(root_env.password),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                roles=[role],
                is_active=True,
                is_superuser=True,
                is_protected=True,  # Prevent accidental deletion
            )
            session.add(new_user)
            await session.commit()
            logger.info(f"Created root user: {root_env.username}")

        except SQLAlchemyError as e:
            logger.error("Root user creation failed")
            await session.rollback()
            raise RuntimeError("Database error during user creation") from e

    async def _warn_env_exposure(self, root_env: RootUserEnv) -> None:
        """
        Generates security warnings about .env file exposure if credentials exist.

        Args:
            root_env: Root environment configuration
        """
        env_path = ".env"
        if not os.path.exists(env_path):
            return

        warning_msg = (
            "SECURITY WARNING: Environment file '.env' contains active root credentials. "
            "Remove root credentials from '.env' in production environments."
        )
        logger.warning(warning_msg)

    async def run(self) -> None:
        """
        Main initialization workflow:
        1. Check for existing users
        2. Validate environment configuration
        3. Create root role and user
        4. Initialize access policies
        5. Start policy synchronization
        6. Generate security warnings

        Raises:
            RuntimeError: For critical initialization failures
        """
        try:
            async with get_sql_session() as session:
                # Check if system is already initialized
                user_count = await session.scalar(select(func.count(User.id)))
                root_env = RootUserEnv()

                if user_count and user_count > 0:
                    logger.info("Existing users found - skipping root initialization")
                    return

                # New system initialization
                logger.info("Initializing authentication system")

                # Create root role and user
                root_role = await self._create_root_role(root_env, session)
                await self._create_root_user(session, root_env, root_role)

                # Initialize access policies
                await init_root_policies(root_env)

                # Start policy synchronization listener
                casbin_enforcer = await get_enforcer()
                await start_redis_policy_listener(casbin_enforcer)

                logger.success("Authentication system initialized")
                await self._warn_env_exposure(root_env)

        except SQLAlchemyError as e:
            logger.critical(f"Database error: {str(e)}")
            raise RuntimeError("Database operation failed") from e
        except Exception as e:
            logger.critical(f"Initialization failed: {str(e)}")
            raise RuntimeError("System initialization aborted") from e


class TokenCleanUpHook(AddonSetupHook):
    """Periodic hook to clean up expired tokens from the database."""

    async def run(self):
        """Executes token cleanup process."""
        try:
            await cleanup_expired_tokens()
            logger.debug("Expired tokens cleaned up successfully")
        except Exception as e:
            logger.error(f"Token cleanup failed: {str(e)}")


class KeyManagerInitHook(AddonSetupHook):
    """Initialization hook for JWT key manager."""

    async def run(self):
        """Initializes the key manager with database session."""
        try:
            await key_manager.initialize()
            logger.info("Key manager initialized successfully")
        except Exception as e:
            logger.critical(f"Key manager initialization failed: {str(e)}")
            raise RuntimeError("Key manager setup failed") from e
