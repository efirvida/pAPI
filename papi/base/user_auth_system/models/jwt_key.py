from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .base import Base


class JWTKey(Base):
    """
    Represents a JWT signing key for token validation and rotation.

    This model stores cryptographic keys used for signing and verifying JWTs,
    enabling secure key rotation practices. Each key record contains:

    - A unique cryptographic key string
    - Timestamp of when the key was created
    - Automatic key rotation capabilities

    Attributes:
        id: Auto-incrementing primary key
        key: Base64-encoded cryptographic key material (512-bit equivalent)
        created_at: UTC timestamp of key creation (automatically set)
    """

    __tablename__ = "jwt_keys"
    __table_args__ = {"comment": "Stores cryptographic keys for JWT signing"}

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="Auto-incrementing primary key identifier",
    )
    key = Column(
        String(128),  # Base64 encoded 512-bit key (64 bytes * 8 = 512 bits)
        nullable=False,
        unique=True,
        comment="Base64-encoded cryptographic key material for JWT signing",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # Use database server time
        nullable=False,
        comment="UTC timestamp of when the key was generated",
    )

    def __repr__(self) -> str:
        """Provides developer-friendly representation of key instance."""
        return f"<JWTKey(id={self.id}, created_at={self.created_at.isoformat()})>"
