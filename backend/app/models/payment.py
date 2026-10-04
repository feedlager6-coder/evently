import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentOrderStatus(str, Enum):
    PENDING = "pending"
    WAITING_FOR_PAYMENT = "waiting_for_payment"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    FAILED = "failed"
    REFUNDED = "refunded"


class ReceiptStatus(str, Enum):
    PENDING = "pending"
    ISSUED = "issued"
    NOT_REQUIRED = "not_required"


class PaymentOperationType(str, Enum):
    PAYMENT = "payment"
    REFUND = "refund"
    RECONCILIATION = "reconciliation"


class WebhookProcessingStatus(str, Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


class PaymentOrder(Base):
    """
    Represents an organizer purchase order for an Ivently Pro entitlement period.
    Connected to a specific Organization and initiated by an authorized User.
    """
    __tablename__ = "payment_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    amount = Column(Float, nullable=False, default=499.0)
    currency = Column(String(3), nullable=False, default="RUB")
    provider = Column(String(50), nullable=False, default="yookassa")
    provider_payment_id = Column(String(100), nullable=True, unique=True, index=True)
    idempotency_key = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default=PaymentOrderStatus.PENDING.value, index=True)

    customer_email = Column(String(255), nullable=True)
    service_name = Column(String(255), nullable=False, default="Ivently Pro — доступ на 30 дней")
    confirmation_url = Column(String(1024), nullable=True)

    paid_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    receipt_status = Column(String(30), nullable=False, default=ReceiptStatus.PENDING.value, index=True)
    receipt_url = Column(String(1024), nullable=True)
    receipt_issued_at = Column(DateTime(timezone=True), nullable=True)

    pro_extended_at = Column(DateTime(timezone=True), nullable=True)
    success_notified_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    organization = relationship("Organization")
    user = relationship("User")
    transactions = relationship("PaymentTransaction", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_payment_orders_org_status", "organization_id", "status"),
        Index("idx_payment_orders_provider_status", "provider", "status"),
    )

    def __repr__(self) -> str:
        return f"<PaymentOrder(id='{self.id}', org='{self.organization_id}', amount={self.amount}, status='{self.status}')>"


class PaymentTransaction(Base):
    """
    Immutable financial audit trail recording all provider status transitions and actions.
    Never stores card numbers, CVVs, or secret tokens.
    """
    __tablename__ = "payment_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_order_id = Column(
        String(36),
        ForeignKey("payment_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    provider = Column(String(50), nullable=False, default="yookassa")
    provider_payment_id = Column(String(100), nullable=True, index=True)
    operation_type = Column(String(50), nullable=False, default=PaymentOperationType.PAYMENT.value)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="RUB")
    status = Column(String(30), nullable=False)
    provider_status = Column(String(50), nullable=True)
    raw_metadata_safe = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    order = relationship("PaymentOrder", back_populates="transactions")

    __table_args__ = (
        Index("idx_payment_transactions_order_created", "payment_order_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<PaymentTransaction(id='{self.id}', order='{self.payment_order_id}', op='{self.operation_type}', status='{self.status}')>"


class PaymentWebhookLog(Base):
    """
    Audit log for inbound payment webhooks ensuring idempotency and replay protection.
    """
    __tablename__ = "payment_webhook_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(50), nullable=False, default="yookassa")
    event_id = Column(String(100), nullable=True, index=True)
    provider_payment_id = Column(String(100), nullable=True, index=True)
    event_type = Column(String(100), nullable=False)
    received_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_status = Column(String(30), nullable=False, default=WebhookProcessingStatus.RECEIVED.value)
    error_message = Column(Text, nullable=True)
    payload_sanitized = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_payment_webhook_logs_event_provider", "event_id", "provider"),
    )

    def __repr__(self) -> str:
        return f"<PaymentWebhookLog(id='{self.id}', event='{self.event_type}', status='{self.processing_status}')>"
