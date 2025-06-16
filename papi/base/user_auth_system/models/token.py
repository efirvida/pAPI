import hashlib

from sqlalchemy import Boolean, Column, DateTime, Index, String
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class RefreshToken(Base):
    """
    Represents a refresh token for JWT authentication.

    Stores refresh tokens with security features:
    - SHA-256 token hashing (prevents plaintext storage)
    - Device binding
    - Revocation tracking
    - Automatic expiration

    Attributes:
        jti: Unique token identifier (primary key)
        subject: User identifier (typically username)
        token_hash: SHA-256 hash of token value
        device_id: Associated device identifier
        user_agent: Client browser/device info
        revoked: Revocation status
        expires_at: Token expiration timestamp
        created_at: Token creation timestamp
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_token_subject_device", "subject", "device_id"),
        Index("ix_refresh_token_expiration", "expires_at"),
        {"comment": "Stores refresh tokens with security features"},
    )

    jti = Column(
        String(44),  # Base64 URL-safe encoded 32-byte token (44 chars)
        primary_key=True,
        index=True,
        comment="Unique token identifier (JWT ID)",
    )
    subject = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier (subject claim)",
    )
    token_hash = Column(
        String(64),  # SHA-256 produces 64-character hex digest
        nullable=False,
        unique=True,
        comment="SHA-256 hash of token value",
    )
    device_id = Column(
        String(36),  # UUID length
        nullable=False,
        comment="Associated device identifier",
    )
    user_agent = Column(
        String(500), nullable=True, comment="Client browser/device information"
    )
    revoked = Column(
        Boolean, default=False, nullable=False, comment="Revocation status flag"
    )

    revoked_at = Column(
        DateTime(timezone=True), nullable=True, comment="Token revocation timestamp"
    )
    expires_at = Column(
        DateTime(timezone=True), nullable=False, comment="Token expiration timestamp"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # Use database server time
        nullable=False,
        comment="Token creation timestamp",
    )

    def __repr__(self) -> str:
        """Provides developer-friendly representation."""
        return (
            f"<RefreshToken(subject='{self.subject}', "
            f"device='{self.device_id}', "
            f"expires={self.expires_at.isoformat()})>"
        )

    @staticmethod
    def compute_token_hash(token: str) -> str:
        """
        Computes SHA-256 hash of a token for secure storage.

        Args:
            token: Raw token string

        Returns:
            64-character hexadecimal digest of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()


class AccessToken(Base):
    """
    Represents an access token for JWT authentication.

    Stores access token metadata with:
    - Device binding
    - Revocation tracking
    - Expiration enforcement
    - Audit capabilities

    Attributes:
        jti: Unique token identifier (primary key)
        subject: User identifier
        device_id: Associated device identifier
        revoked: Revocation status
        expires_at: Token expiration timestamp
        revoked_at: Timestamp of revocation
        created_at: Token creation timestamp
    """

    __tablename__ = "access_tokens"
    __table_args__ = (
        Index("ix_access_tokens_subject_device", "subject", "device_id"),
        Index("ix_access_tokens_expiration", "expires_at"),
        {"comment": "Stores access token metadata"},
    )

    jti = Column(
        String(44),  # Base64 URL-safe encoded 32-byte token
        primary_key=True,
        index=True,
        unique=True,
        comment="Unique token identifier (JWT ID)",
    )
    subject = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier (subject claim)",
    )
    device_id = Column(
        String(36),  # UUID length
        nullable=False,
        comment="Associated device identifier",
    )
    revoked = Column(
        Boolean, default=False, nullable=False, comment="Revocation status flag"
    )

    expires_at = Column(
        DateTime(timezone=True), nullable=False, comment="Token expiration timestamp"
    )
    revoked_at = Column(
        DateTime(timezone=True), nullable=True, comment="Timestamp of revocation"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # Use database server time
        nullable=False,
        comment="Token creation timestamp",
    )

    def __repr__(self) -> str:
        """Provides developer-friendly representation."""
        status = "REVOKED" if self.revoked else "ACTIVE"
        return (
            f"<AccessToken(subject='{self.subject}', "
            f"device='{self.device_id}', "
            f"status={status}, "
            f"expires={self.expires_at.isoformat()})>"
        )
