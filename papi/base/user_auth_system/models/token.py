from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token = Column(String, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    jti = Column(String, unique=True, nullable=False)
    device_id = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return (
            f"<RefreshToken(subject='{self.subject}', jti='{self.jti}', "
            f"revoked={self.revoked}, expires_at={self.expires_at})>"
        )


class AccessToken(Base):
    __tablename__ = "access_tokens"

    jti = Column(String, primary_key=True, index=True, unique=True)
    subject = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    blacklisted = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_access_tokens_subject_expires_at", "subject", "expires_at"),
    )

    def __repr__(self):
        return (
            f"<AccessToken(subject='{self.subject}', jti='{self.jti}', "
            f"blacklisted={self.blacklisted}, expires_at={self.expires_at})>"
        )
