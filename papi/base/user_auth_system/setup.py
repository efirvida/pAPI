import getpass
import logging
import os
import re
from datetime import datetime
from typing import Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from papi.core.addons import AddonSetupHook
from papi.core.db import get_sql_session
from papi.core.settings import get_config
from user_auth_system.models import Role, User
from user_auth_system.schemas.policy import PolicyCreate
from user_auth_system.security.casbin_policies import (
    add_policy,
    start_redis_policy_listener,
)
from user_auth_system.security.enforcer import get_enforcer
from user_auth_system.security.enums import PolicyAction, PolicyEffect
from user_auth_system.security.password import hash_password

config = get_config()
logger = logging.getLogger(__name__)

# Email validation regex (RFC 5322 compliant, simplified)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def is_valid_email(email: str) -> bool:
    """Validate email format using regex."""
    return bool(EMAIL_REGEX.fullmatch(email))


async def init_root_policies() -> None:
    """
    Initializes the default Casbin policy that grants full access to users with the 'root' role.
    """
    root_policy = PolicyCreate(
        subject="root",
        object="/*",
        action=PolicyAction.ALL,
        condition="True",
        effect=PolicyEffect.ALLOW,
    )

    try:
        inserted = await add_policy(root_policy)

        if inserted:
            logger.info("Root policy added successfully.")
        else:
            logger.info("Root policy already exists. Skipping insertion.")

    except Exception as e:
        logger.exception("Failed to initialize root Casbin policy.")
        raise RuntimeError("Policy initialization failed.") from e


class AuthSystemInitializer(AddonSetupHook):
    """
    Initializes root user and Casbin policies if the system is empty.
    Supports both production (env-based) and development (interactive) modes.
    """

    async def _get_root_credentials(self) -> Tuple[str, str]:
        """
        Retrieve root user credentials from environment (production)
        or prompt interactively (development).
        """
        is_prod = os.getenv("ENV", "").lower() == "production"
        logger.info("Environment mode: %s", "production" if is_prod else "development")

        if is_prod:
            email = os.getenv("ROOT_EMAIL", "").strip()
            password = os.getenv("ROOT_PASSWORD", "").strip()

            if not email or not password:
                logger.critical("Missing ROOT_EMAIL or ROOT_PASSWORD in production")
                raise EnvironmentError("Missing root credentials")

            if not is_valid_email(email):
                raise ValueError("Invalid email format for ROOT_EMAIL")

            return email, password

        # Interactive mode for development
        while True:
            email = input("Enter email for root user: ").strip()
            if is_valid_email(email):
                break
            print("Invalid email format. Please try again.")

        while True:
            password = getpass.getpass("Enter password for root user: ")
            if password:
                break
            print("Password cannot be empty.")

        return email, password

    async def _create_root_role(self, session: AsyncSession) -> Role:
        """
        Ensure the 'root' role exists in the database.
        Returns the Role instance.
        """
        root_role = await session.scalar(
            select(Role).where(Role.name == "root").limit(1)
        )

        if not root_role:
            root_role = Role(
                name="root", description="Superadmin role with full system access"
            )
            session.add(root_role)
            await session.commit()
            logger.info("Created 'root' role")

        return root_role

    async def _create_root_user(
        self, session: AsyncSession, email: str, password: str, root_role: Role
    ) -> None:
        """
        Creates the root user with superuser privileges.
        """
        root_user = User(
            username="root",
            full_name="Root Administrator",
            email=email,
            hashed_password=hash_password(password),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            roles=[root_role],
            is_active=True,
            is_superuser=True,
        )
        session.add(root_user)
        await session.commit()
        logger.info("Root user created successfully")

    async def run(self) -> None:
        """
        Entry point to run the initialization logic.
        Creates root role, root user, and Casbin policies.
        """
        try:
            async with get_sql_session() as session:
                user_count = await session.scalar(
                    select(func.count()).select_from(User)
                )

                if user_count and user_count > 0:
                    logger.info("Users exist, skipping root user creation")
                    await init_root_policies()
                    return

                email, password = await self._get_root_credentials()
                root_role = await self._create_root_role(session)
                casbin_policy_enforcer = await get_enforcer()
                await self._create_root_user(session, email, password, root_role)
                await init_root_policies()
                await start_redis_policy_listener(casbin_policy_enforcer)

        except SQLAlchemyError as db_err:
            logger.exception("❌ Database error during initialization")
            raise RuntimeError("Database initialization failed") from db_err
        except Exception:
            logger.exception("❌ Unexpected error during initialization")
            raise
