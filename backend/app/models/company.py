import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventCompanyProfile(Base):
    """
    Explicit event-scoped opt-in by a user to find a companion for a specific event.
    'Хочу пойти' or 'Я иду' does NOT automatically create or activate this profile.
    """
    __tablename__ = "event_company_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    note = Column(String(140), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="company_profiles")
    user = relationship("User", back_populates="company_profiles")

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_company_profile"),
        Index("idx_company_profiles_feed", "event_id", "is_active", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EventCompanyProfile(event_id='{self.event_id}', user_id={self.user_id}, is_active={self.is_active})>"


class EventCompanyRequest(Base):
    """
    Connection/companion request sent by user A to user B for a specific event.
    Status transitions: pending -> accepted | declined | cancelled.
    """
    __tablename__ = "event_company_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="company_requests")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_company_requests")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_company_requests")
    match = relationship("EventCompanyMatch", back_populates="request", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("event_id", "sender_id", "receiver_id", name="uq_event_company_request"),
        CheckConstraint("sender_id != receiver_id", name="ck_company_request_no_self"),
        Index("idx_company_requests_receiver", "event_id", "receiver_id", "status"),
        Index("idx_company_requests_sender", "event_id", "sender_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<EventCompanyRequest(event_id='{self.event_id}', sender={self.sender_id}, receiver={self.receiver_id}, status='{self.status}')>"


class EventCompanyMatch(Base):
    """
    Represents mutual agreement between two users to attend an event together.
    Canonical order: user1_id < user2_id to guarantee single symmetrical match record.
    """
    __tablename__ = "event_company_matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user1_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user2_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id = Column(String(36), ForeignKey("event_company_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="company_matches")
    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    request = relationship("EventCompanyRequest", back_populates="match")

    __table_args__ = (
        UniqueConstraint("event_id", "user1_id", "user2_id", name="uq_event_company_match"),
        CheckConstraint("user1_id < user2_id", name="ck_company_match_canonical_order"),
        Index("idx_company_matches_u1", "event_id", "user1_id"),
        Index("idx_company_matches_u2", "event_id", "user2_id"),
    )

    def __repr__(self) -> str:
        return f"<EventCompanyMatch(event_id='{self.event_id}', user1={self.user1_id}, user2={self.user2_id})>"
