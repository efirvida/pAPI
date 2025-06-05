from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    func,
)

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    details = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    timestamp_updated = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
