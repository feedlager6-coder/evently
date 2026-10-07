import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventReminder(Base):
    __tablename__ = "event_reminders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reminded_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    reminder_type = Column(String(30), default="same_day", nullable=False)

    # Relationships
    event = relationship("Event")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", "reminder_type", name="uq_event_user_reminder"),
        Index("idx_event_reminders_event_user", "event_id", "user_id"),
        Index("idx_event_reminders_reminded_at", "reminded_at"),
    )

    def __repr__(self) -> str:
        return f"<EventReminder(id='{self.id}', event_id='{self.event_id}', user_id={self.user_id}, type='{self.reminder_type}')>"
