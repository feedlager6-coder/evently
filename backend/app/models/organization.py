import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index, Integer, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


ORGANIZATION_CATEGORIES = [
    "Кафе",
    "Ресторан",
    "Бар",
    "Клуб",
    "Концертная площадка",
    "Театр",
    "Спорт",
    "Образование",
    "Культура",
    "Другое"
]


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)
    city_id = Column(String(50), ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True)
    address = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    website = Column(String(1024), nullable=True)
    social_link = Column(String(1024), nullable=True)
    status = Column(String(20), nullable=False, default=OrganizationStatus.ACTIVE.value, index=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="owned_organizations")
    city = relationship("City")
    events = relationship("Event", back_populates="organization")
    subscriptions = relationship("Subscription", back_populates="organization", cascade="all, delete-orphan")
    plan_record = relationship("OrganizationPlan", back_populates="organization", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_organizations_owner_status", "owner_user_id", "status"),
        Index("idx_organizations_city_status", "city_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Organization(id='{self.id}', name='{self.name}', slug='{self.slug}', status='{self.status}')>"
