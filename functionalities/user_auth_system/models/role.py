from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from .base import Base

# Solución: Usar extend_existing=True para permitir la redefinición
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to users table",
    ),
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to roles table",
    ),
    comment="Many-to-many relationship between users and roles",
    extend_existing=True,
)


class Role(Base):
    """
    Represents a user role with specific permissions and access rights.

    Attributes:
        id: Auto-incrementing primary key
        name: Unique role identifier (e.g., 'admin', 'user')
        description: Human-readable role description
        is_protected: Flag indicating system-protected roles (cannot be deleted)
        users: Relationship to users assigned to this role

    System-protected roles:
    - Prevent accidental deletion of critical roles
    - Typically include 'admin', 'superuser', or other core roles
    """

    __tablename__ = "roles"
    __table_args__ = {"comment": "Stores user roles and permissions"}

    id = Column(
        Integer, primary_key=True, index=True, comment="Auto-incrementing primary key"
    )
    name = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="Unique role identifier (e.g., 'admin', 'user')",
    )
    description = Column(
        String(255), nullable=True, comment="Human-readable role description"
    )
    is_protected = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Flag indicating system-protected roles (cannot be deleted)",
    )

    users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        passive_deletes=True,
        cascade="save-update, merge",  # Cambiado por seguridad
    )

    def __repr__(self) -> str:
        """Provides developer-friendly representation."""
        return f"<Role(name='{self.name}', protected={self.is_protected})>"
