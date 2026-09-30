import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    cover_image_url = Column(String(1024), nullable=True)
    category_id = Column(String(50), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    city_id = Column(String(50), ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False, index=True)
    start_at = Column(DateTime(timezone=True), nullable=False, index=True)
    venue_name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    price_amount = Column(Float, nullable=True)
    price_currency = Column(String(10), nullable=True)
    status = Column(String(20), nullable=False, default=EventStatus.PENDING.value, index=True)
    organizer_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    city = relationship("City", back_populates="events")
    category = relationship("Category", back_populates="events")
    organizer = relationship("User", back_populates="organized_events", foreign_keys=[organizer_user_id])
    organization = relationship("Organization", back_populates="events")
    attendees = relationship("EventAttendee", back_populates="event", cascade="all, delete-orphan")
    interests = relationship("EventInterest", back_populates="event", cascade="all, delete-orphan")
    company_profiles = relationship("EventCompanyProfile", back_populates="event", cascade="all, delete-orphan")
    company_requests = relationship("EventCompanyRequest", back_populates="event", cascade="all, delete-orphan")
    company_matches = relationship("EventCompanyMatch", back_populates="event", cascade="all, delete-orphan")
    views = relationship("EventView", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_events_discovery", "city_id", "status", "start_at"),
    )

    def __repr__(self) -> str:
        return f"<Event(id='{self.id}', title='{self.title}', status='{self.status}', city='{self.city_id}')>"
