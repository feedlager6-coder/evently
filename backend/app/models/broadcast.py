import secrets
import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BroadcastTargetType(str, Enum):
    ORGANIZATION_SUBSCRIBERS = "organization_subscribers"
    EVENT_INTEREST = "event_interest"


class BroadcastType(str, Enum):
    MARKETING = "marketing"
    TRANSACTIONAL = "transactional"


class BroadcastTemplateKey(str, Enum):
    EVENT_ANNOUNCEMENT = "event_announcement"
    EVENT_UPDATE = "event_update"
    CUSTOM_UPDATE = "custom_update"


class BroadcastStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecipientStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    BLOCKED = "blocked"


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    target_type = Column(String(50), nullable=False, default=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value)
    broadcast_type = Column(String(30), nullable=False, default=BroadcastType.MARKETING.value)
    template_key = Column(String(50), nullable=False, default=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value)
    custom_text = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default=BroadcastStatus.QUEUED.value, index=True)
    attribution_token = Column(String(32), unique=True, index=True, nullable=True, default=lambda: secrets.token_hex(8))

    total_recipients = Column(Integer, nullable=False, default=0)
    sent_count = Column(Integer, nullable=False, default=0)
    delivered_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    blocked_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization")
    created_by_user = relationship("User")
    event = relationship("Event")
    recipients = relationship("BroadcastRecipient", back_populates="broadcast", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_broadcasts_org_created", "organization_id", "created_at"),
        Index("idx_broadcasts_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Broadcast(id='{self.id}', org='{self.organization_id}', status='{self.status}')>"


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    broadcast_id = Column(String(36), ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=RecipientStatus.PENDING.value, index=True)
    telegram_message_id = Column(BigInteger, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    attributed_interest_at = Column(DateTime(timezone=True), nullable=True)
    attributed_rsvp_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    broadcast = relationship("Broadcast", back_populates="recipients")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_recipient"),
        Index("idx_broadcast_recipients_user_sent", "user_id", "sent_at"),
        Index("idx_broadcast_recipients_broadcast_status", "broadcast_id", "status"),
        Index("idx_broadcast_recipients_attr", "user_id", "broadcast_id", "opened_at"),
    )

    def __repr__(self) -> str:
        return f"<BroadcastRecipient(broadcast='{self.broadcast_id}', user={self.user_id}, status='{self.status}')>"
