import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventView(Base):
    __tablename__ = "event_views"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    source = Column(String(30), nullable=True, default="unknown")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    event = relationship("Event", back_populates="views")
    user = relationship("User")

    __table_args__ = (
        Index("idx_event_views_event_created", "event_id", "created_at"),
        Index("idx_event_views_dedup", "event_id", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EventView(id='{self.id}', event_id='{self.event_id}', user_id={self.user_id}, source='{self.source}')>"
