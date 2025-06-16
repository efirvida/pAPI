from sqlalchemy import Boolean, Column, DateTime, Integer, String, func, select
from sqlalchemy.orm import relationship

from papi.core.db import get_sql_session

from .base import Base
from .casbin import AuthRules
from .group import user_groups
from .role import user_roles


class User(Base):
    """
    Represents a system user with authentication capabilities and access control.

    Attributes:
        id: Unique user identifier
        username: Unique username for authentication
        email: Unique email address
        avatar: URL to user avatar image
        full_name: User's full name
        hashed_password: Securely hashed password
        is_active: Account activation status
        is_superuser: Superuser privileges flag
        created_at: Account creation timestamp
        updated_at: Last account update timestamp
        roles: Assigned security roles
        groups: Membership in user groups

    Relationships:
        roles: Many-to-many relationship with Role
        groups: Many-to-many relationship with Group
    """

    __tablename__ = "users"
    __table_args__ = {"comment": "Stores system user accounts and credentials"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="Auto-incrementing unique user ID",
    )
    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique username for authentication",
    )
    email = Column(
        String(255),
        unique=True,
        index=True,
        comment="Unique email address for account recovery",
    )
    avatar = Column(String(512), nullable=True, comment="URL to user avatar image")
    full_name = Column(String(100), nullable=True, comment="User's full name")
    hashed_password = Column(
        String(128), nullable=False, comment="BCrypt hashed password"
    )
    is_active = Column(
        Boolean,
        default=True,
        server_default="true",
        comment="Account activation status (false = disabled)",
    )
    is_superuser = Column(
        Boolean,
        default=False,
        server_default="false",
        comment="Superuser privileges flag",
    )
    is_protected = Column(
        Boolean,
        default=False,
        server_default="false",
        comment="System-protected account flag (cannot be deleted)",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Account creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last account update timestamp",
    )
    roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
        cascade="save-update, merge",
        passive_deletes=True,
    )
    groups = relationship(
        "Group",
        secondary=user_groups,
        back_populates="users",
        lazy="selectin",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    async def get_applicable_rules(self) -> list[dict]:
        """
        Retrieves all Casbin policy rules that apply to the user, including:
        - Direct user assignments
        - Role-based assignments
        - Group-based assignments
        - Group role-based assignments

        Returns:
            List of policy rules as dictionaries with keys:
            - v0: Subject (user, role, or group)
            - v1: Object/resource
            - v2: Action
            - v3: Condition
            - v4: Effect (allow/deny)
            - v5: Additional context
        """
        subjects = set()

        subjects.add(self.username)

        for role in self.roles:
            subjects.add(f"role:{role}")

        for group in self.groups:
            subjects.add(f"group:{group.name}")

        query = select(AuthRules).where(
            AuthRules.ptype == "p", AuthRules.v0.in_(list(subjects))
        )

        async with get_sql_session() as session:
            result = await session.execute(query)
            rules = result.scalars().all()

        return [
            {
                "v0": rule.v0,
                "v1": rule.v1,
                "v2": rule.v2,
                "v3": rule.v3,
                "v4": rule.v4,
                "v5": rule.v5,
            }
            for rule in rules
        ]

    async def get_permissions(self) -> list[tuple]:
        """
        Gets simplified permissions in (resource, action) format

        Returns:
            List of tuples: [(resource, action), ...]
        """
        rules = await self.get_applicable_rules()
        return list(set((rule["v1"], rule["v2"]) for rule in rules))

    async def has_permission(self, resource: str, action: str) -> bool:
        """
        Checks if user has permission for a specific resource-action pair

        Args:
            resource: Resource path (e.g., "/users")
            action: Action (e.g., "read", "write")

        Returns:
            True if permission is granted, False otherwise
        """
        permissions = await self.get_permissions()
        return (resource, action) in permissions

    async def get_allowed_resources(self) -> dict[str, list[str]]:
        """
        Gets all allowed resources and actions

        Returns:
            Dictionary: {resource: [actions]}
        """
        rules = await self.get_applicable_rules()
        resources = {}

        for rule in rules:
            if rule["v4"] == "allow":
                resource = rule["v1"]
                action = rule["v2"]

                if resource not in resources:
                    resources[resource] = []

                if action not in resources[resource]:
                    resources[resource].append(action)

        return resources

    def __repr__(self) -> str:
        """Provides developer-friendly representation."""
        status = "active" if self.is_active else "inactive"
        return f"<User(username='{self.username}', status={status})>"
