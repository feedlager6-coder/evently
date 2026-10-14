import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketCheckIn(Base):
    __tablename__ = "ticket_checkins"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_code = Column(String(255), nullable=False, index=True)
    checked_in_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    guest_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "ticket_code", name="uq_ticket_checkins_event_code"),
    )

    def __repr__(self) -> str:
        return f"<TicketCheckIn(event_id='{self.event_id}', ticket_code='{self.ticket_code}', created_at={self.created_at})>"
