import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventInterest(Base):
    __tablename__ = "event_interests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="interests")
    user = relationship("User", back_populates="interests")

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_user_interest"),
        Index("idx_event_interests_event_id", "event_id"),
        Index("idx_event_interests_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<EventInterest(id='{self.id}', event_id='{self.event_id}', user_id={self.user_id})>"
