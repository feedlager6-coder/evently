import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    organization = relationship("Organization", back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_user_organization_subscription"),
        Index("idx_subscriptions_org_user", "organization_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Subscription(id='{self.id}', user_id={self.user_id}, organization_id='{self.organization_id}')>"
