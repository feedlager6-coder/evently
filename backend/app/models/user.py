from datetime import datetime, timezone
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    default_city_id = Column(String(50), ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    default_city = relationship("City", back_populates="users")
    organized_events = relationship("Event", back_populates="organizer", foreign_keys="Event.organizer_user_id")
    attendances = relationship("EventAttendee", back_populates="user", cascade="all, delete-orphan")
    owned_organizations = relationship("Organization", back_populates="owner", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    interests = relationship("EventInterest", back_populates="user", cascade="all, delete-orphan")
    company_profiles = relationship("EventCompanyProfile", back_populates="user", cascade="all, delete-orphan")
    sent_company_requests = relationship("EventCompanyRequest", foreign_keys="EventCompanyRequest.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_company_requests = relationship("EventCompanyRequest", foreign_keys="EventCompanyRequest.receiver_id", back_populates="receiver", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"
