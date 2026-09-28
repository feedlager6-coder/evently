from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventAttendee(Base):
    __tablename__ = "event_attendees"

    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="attendees")
    user = relationship("User", back_populates="attendances")

    def __repr__(self) -> str:
        return f"<EventAttendee(event_id='{self.event_id}', user_id={self.user_id})>"
