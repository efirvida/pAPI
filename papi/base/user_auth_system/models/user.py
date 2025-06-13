from sqlalchemy import Boolean, Column, DateTime, Integer, String, func, select
from sqlalchemy.orm import relationship

from papi.core.db import get_sql_session

from .base import Base
from .casbin import AuthRules
from .group import user_groups
from .role import user_roles


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, index=True)
    avatar = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    roles = relationship(
        "Role", secondary=user_roles, back_populates="users", lazy="selectin"
    )
    groups = relationship(
        "Group", secondary=user_groups, back_populates="users", lazy="selectin"
    )

    @property
    async def casbin_assignments(self) -> list[str]:
        """Retrieves all user role and group assignments from Casbin.

        Returns:
            list[str]: List of role and group assignments in Casbin format
                      (e.g., 'role:admin', 'group:users')
        """
        async with get_sql_session() as s:
            stmt = select(AuthRules.v1).where(
                AuthRules.ptype == "g", AuthRules.v0 == self.username
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    @property
    async def casbin_roles(self) -> list[str]:
        """Gets list of role names assigned to the user.

        Returns:
            list[str]: List of role names without the 'role:' prefix
        """
        assignments = await self.casbin_assignments
        return [r[5:] for r in assignments if r.startswith("role:")]

    @property
    async def casbin_groups(self) -> list[str]:
        """Gets list of group names the user belongs to.

        Returns:
            list[str]: List of group names without the 'group:' prefix
        """
        assignments = await self.casbin_assignments
        return [g[6:] for g in assignments if g.startswith("group:")]
