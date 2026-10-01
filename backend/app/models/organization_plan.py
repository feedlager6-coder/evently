import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlanType(str, Enum):
    FREE = "free"
    PRO = "pro"


class PlanStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OrganizationPlan(Base):
    """
    Stores subscription plan and entitlement lifecycle for an organization.
    Multi-org safe: entitlements belong to the organization, not the user.
    """
    __tablename__ = "organization_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    plan = Column(String(20), nullable=False, default=PlanType.FREE.value)
    status = Column(String(20), nullable=False, default=PlanStatus.ACTIVE.value)
    starts_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="plan_record")

    __table_args__ = (
        Index("idx_organization_plans_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<OrganizationPlan(org='{self.organization_id}', plan='{self.plan}', status='{self.status}')>"
