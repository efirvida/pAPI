from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base

user_groups = Table(
    "user_groups",
    Base.metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to users table",
    ),
    Column(
        "group_id",
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Foreign key to groups table",
    ),
    comment="Many-to-many relationship between users and groups",
    extend_existing=True,
)


class Group(Base):
    """
    Represents a user group for organizing users and managing permissions.

    Attributes:
        id: Auto-incrementing primary key
        name: Unique group identifier
        description: Human-readable group description
        is_system_group: Flag indicating system-protected groups
        users: Relationship to users belonging to this group

    System-protected groups:
    - Prevent accidental deletion of critical groups
    - Typically include 'admins', 'managers', or other core groups
    """

    __tablename__ = "groups"
    __table_args__ = {
        "comment": "Stores user groups for organization and access control"
    }

    id = Column(
        Integer, primary_key=True, index=True, comment="Auto-incrementing primary key"
    )
    name = Column(
        String(100), unique=True, nullable=False, comment="Unique group identifier"
    )
    description = Column(
        String(255), nullable=True, comment="Human-readable group description"
    )

    is_protected = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Flag indicating system-protected groups (cannot be deleted)",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp of group creation",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp of last group update",
    )

    users = relationship(
        "User",
        secondary=user_groups,
        back_populates="groups",
        cascade="all, delete",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        """Provides developer-friendly representation."""
        return f"<Group(name='{self.name}', system={self.is_system_group})>"
