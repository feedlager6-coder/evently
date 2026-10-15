import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from app.config import settings
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_plan import OrganizationPlan, PlanType, PlanStatus
from app.models.user import User
from app.models.payment import (
    PaymentOrder,
    PaymentTransaction,
    PaymentWebhookLog,
    PaymentOrderStatus,
    ReceiptStatus,
    PaymentOperationType,
    WebhookProcessingStatus,
)
from app.services.payment.base import PaymentProvider, ProviderPaymentResult
from app.services.payment.yookassa import YooKassaProvider
from app.services.notification_service import send_telegram_notification

logger = logging.getLogger("evently.payments")

# Optional active provider override for test suite injection
_PROVIDER_OVERRIDE: Optional[PaymentProvider] = None


def set_payment_provider_override(provider: Optional[PaymentProvider]) -> None:
    """Sets a mock or custom provider instance for testing."""
    global _PROVIDER_OVERRIDE
    _PROVIDER_OVERRIDE = provider


def get_payment_provider() -> PaymentProvider:
    """
    Returns active PaymentProvider instance.
    Uses test override if set, otherwise instantiates YooKassaProvider with configured settings.
    """
    global _PROVIDER_OVERRIDE
    if _PROVIDER_OVERRIDE is not None:
        return _PROVIDER_OVERRIDE

    if not settings.is_yookassa_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Платёжная система не настроена на сервере."
        )

    return YooKassaProvider(
        shop_id=settings.YOOKASSA_SHOP_ID,
        secret_key=settings.YOOKASSA_SECRET_KEY
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_customer_email(email: Optional[str]) -> Optional[str]:
    """Validates and standardizes optional customer email for receipt issuance."""
    if not email:
        return None
    clean = email.strip()
    if not clean:
        return None
    # RFC 5322 simplified pattern
    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not re.match(email_regex, clean) or len(clean) > 255:
        raise HTTPException(
            status_code=422,
            detail="Некорректный формат email для чека."
        )
    return clean.lower()


class PaymentService:
    """
    Production Payment & Pro Subscription Lifecycle Engine.
    Handles order creation, idempotency, YooKassa webhook processing,
    atomic Pro extensions on OrganizationPlan, and assisted self-employed receipts.
    """

    @classmethod
    async def create_pro_order(
        cls,
        session: AsyncSession,
        organization_id: str,
        user: User,
        customer_email: Optional[str] = None,
        provider: Optional[PaymentProvider] = None
    ) -> Tuple[PaymentOrder, str]:
        """
        Creates a new Pro purchase order and initiates checkout with YooKassa.
        Guards:
        1. Organization ownership verification.
        2. Feature flag enforcement (PAYMENTS_ENABLED).
        3. Pending order reuse (anti-duplicate click within 15 min TTL).
        """
        # 1. Ownership & Organization check
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org = (await session.execute(org_stmt)).scalar_one_or_none()
        if not org or org.status == OrganizationStatus.DELETED.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")

        if org.owner_user_id != user.id and not settings.is_admin(user.telegram_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не являетесь владельцем этой организации"
            )

        # 2. Feature flag check
        if not settings.PAYMENTS_ENABLED and not settings.is_admin(user.telegram_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Оплата Pro временно недоступна."
            )

        validated_email = validate_customer_email(customer_email)
        active_provider = provider or get_payment_provider()

        # 3. Anti-duplicate order check: reuse pending order if within TTL
        now = utc_now()
        fifteen_mins_ago = now - timedelta(minutes=15)
        existing_order_stmt = select(PaymentOrder).where(
            PaymentOrder.organization_id == organization_id,
            PaymentOrder.status.in_([
                PaymentOrderStatus.PENDING.value,
                PaymentOrderStatus.WAITING_FOR_PAYMENT.value
            ]),
            PaymentOrder.created_at >= fifteen_mins_ago,
            PaymentOrder.confirmation_url.is_not(None)
        ).order_by(desc(PaymentOrder.created_at))

        existing_order = (await session.execute(existing_order_stmt)).scalars().first()
        if existing_order and existing_order.confirmation_url:
            is_mock_order = bool(existing_order.provider_payment_id and existing_order.provider_payment_id.startswith("mock_"))
            is_real_yookassa = settings.is_yookassa_configured and settings.PAYMENTS_ENABLED

            # Discard mock order if real YooKassa is now active
            if is_mock_order and is_real_yookassa:
                logger.info("Discarding mock order %s because real YooKassa is active", existing_order.id)
            else:
                try:
                    existing_order = await cls.verify_and_activate_order(session, existing_order)
                except Exception as e:
                    logger.warning("Error verifying existing order %s before reuse: %s", existing_order.id, e)

                if existing_order.status in [
                    PaymentOrderStatus.PENDING.value,
                    PaymentOrderStatus.WAITING_FOR_PAYMENT.value
                ]:
                    logger.info(
                        "Reusing existing pending PaymentOrder %s for organization %s",
                        existing_order.id, organization_id
                    )
                    return existing_order, existing_order.confirmation_url

        # 4. Create new Order
        order_id = str(uuid.uuid4())
        idempotency_key = f"order_{order_id}"
        amount = float(settings.PRO_MONTHLY_PRICE_RUB)
        currency = "RUB"
        description = "Ivently Pro — доступ на 30 дней"

        # Determine return URL: redirect directly back into Telegram Mini App with startapp=payment_{order_id}
        mini_app_base = settings.effective_mini_app_url.split("?")[0].rstrip("/")
        return_url = f"{mini_app_base}?startapp=payment_{order_id}"
        if settings.YOOKASSA_RETURN_URL and "startapp" in settings.YOOKASSA_RETURN_URL:
            return_url = settings.YOOKASSA_RETURN_URL.replace("{order_id}", order_id)

        metadata = {
            "order_id": order_id,
            "organization_id": organization_id,
            "user_id": user.id,
            "app": "ivently"
        }

        try:
            prov_res = await active_provider.create_payment(
                amount=amount,
                currency=currency,
                description=description,
                return_url=return_url,
                idempotency_key=idempotency_key,
                metadata=metadata,
                customer_email=validated_email
            )
        except Exception as e:
            logger.error("Failed to initiate payment with provider: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось создать платёж у провайдера. Попробуйте снова."
            )

        order = PaymentOrder(
            id=order_id,
            organization_id=organization_id,
            user_id=user.id,
            amount=amount,
            currency=currency,
            provider="yookassa",
            provider_payment_id=prov_res.provider_payment_id,
            idempotency_key=idempotency_key,
            status=prov_res.status or PaymentOrderStatus.PENDING.value,
            customer_email=validated_email,
            service_name=description,
            confirmation_url=prov_res.confirmation_url,
            expires_at=now + timedelta(minutes=30),
            receipt_status=ReceiptStatus.PENDING.value,
            created_at=now,
            updated_at=now
        )
        session.add(order)

        # Audit transaction
        tx = PaymentTransaction(
            payment_order_id=order_id,
            provider="yookassa",
            provider_payment_id=prov_res.provider_payment_id,
            operation_type=PaymentOperationType.PAYMENT.value,
            amount=amount,
            currency=currency,
            status=prov_res.status or PaymentOrderStatus.PENDING.value,
            provider_status=prov_res.status,
            raw_metadata_safe=f"checkout_created; confirmation_url={bool(prov_res.confirmation_url)}",
            created_at=now,
            updated_at=now
        )
        session.add(tx)

        await session.commit()
        await session.refresh(order)
        logger.info("Created PaymentOrder %s (provider_id=%s)", order_id, prov_res.provider_payment_id)

        return order, order.confirmation_url or return_url

    @classmethod
    async def reconcile_pending_orders_for_org(
        cls,
        session: AsyncSession,
        organization_id: str
    ) -> List[PaymentOrder]:
        """
        Reconciles pending or waiting_for_payment orders for an organization created in the last 2 hours.
        Queries provider status and activates Pro if payment was completed.
        """
        now = utc_now()
        two_hours_ago = now - timedelta(hours=2)
        stmt = select(PaymentOrder).where(
            PaymentOrder.organization_id == organization_id,
            PaymentOrder.status.in_([
                PaymentOrderStatus.PENDING.value,
                PaymentOrderStatus.WAITING_FOR_PAYMENT.value
            ]),
            PaymentOrder.created_at >= two_hours_ago
        ).order_by(desc(PaymentOrder.created_at))

        orders = list((await session.execute(stmt)).scalars().all())
        updated_orders = []
        for o in orders:
            try:
                verified = await cls.verify_and_activate_order(session, o)
                updated_orders.append(verified)
            except Exception as e:
                logger.warning("Reconciliation error for order %s: %s", o.id, e)
                updated_orders.append(o)
        return updated_orders

    @classmethod
    async def verify_and_activate_order(
        cls,
        session: AsyncSession,
        order: PaymentOrder,
        provider: Optional[PaymentProvider] = None
    ) -> PaymentOrder:
        """
        Verifies payment directly with the provider, extends OrganizationPlan by +30 days,
        records the transaction, and delivers an idempotent confirmation notification.
        Guarantees:
        1. Exact amount and currency match.
        2. Single Pro extension even if called multiple times concurrently.
        3. Single Telegram notification.
        """
        # Idempotency fast-exit
        if order.status == PaymentOrderStatus.SUCCEEDED.value and order.pro_extended_at is not None:
            return order

        active_provider = provider or get_payment_provider()

        if not order.provider_payment_id:
            logger.warning("PaymentOrder %s has no provider_payment_id", order.id)
            return order

        try:
            prov_res = await active_provider.get_payment(order.provider_payment_id)
        except Exception as e:
            logger.error("Failed to query payment status from provider for order %s: %s", order.id, e)
            return order

        now = utc_now()

        # Check for successful payment
        if prov_res.status == "succeeded" and prov_res.paid:
            # 1. Exact amount and currency verification
            from decimal import Decimal
            exp_amount = Decimal(str(order.amount))
            act_amount = Decimal(str(prov_res.amount))
            if abs(act_amount - exp_amount) > Decimal("0.01") or prov_res.currency.upper() != order.currency.upper():
                logger.critical(
                    "SECURITY: Payment amount mismatch for order %s! Expected: %s %s, Got: %s %s",
                    order.id, exp_amount, order.currency, act_amount, prov_res.currency
                )
                order.status = PaymentOrderStatus.FAILED.value
                order.updated_at = now
                session.add(PaymentTransaction(
                    payment_order_id=order.id,
                    provider=order.provider,
                    provider_payment_id=order.provider_payment_id,
                    operation_type=PaymentOperationType.PAYMENT.value,
                    amount=prov_res.amount,
                    currency=prov_res.currency,
                    status=PaymentOrderStatus.FAILED.value,
                    provider_status=prov_res.status,
                    raw_metadata_safe="REJECTED: Amount or currency mismatch",
                    created_at=now,
                    updated_at=now
                ))
                await session.commit()
                return order

            # 2. Idempotent Pro Plan Extension
            if order.pro_extended_at is None:
                plan_stmt = select(OrganizationPlan).where(
                    OrganizationPlan.organization_id == order.organization_id
                )
                plan_record = (await session.execute(plan_stmt)).scalar_one_or_none()

                days_to_add = timedelta(days=settings.PRO_SUBSCRIPTION_DAYS)

                if plan_record:
                    curr_expires = ensure_utc(plan_record.expires_at)
                    if plan_record.plan == PlanType.PRO.value and curr_expires and curr_expires > now:
                        new_expires = curr_expires + days_to_add
                    else:
                        new_expires = now + days_to_add

                    plan_record.plan = PlanType.PRO.value
                    plan_record.status = PlanStatus.ACTIVE.value
                    plan_record.expires_at = new_expires
                    plan_record.updated_at = now
                else:
                    new_expires = now + days_to_add
                    plan_record = OrganizationPlan(
                        organization_id=order.organization_id,
                        plan=PlanType.PRO.value,
                        status=PlanStatus.ACTIVE.value,
                        starts_at=now,
                        expires_at=new_expires,
                        created_at=now,
                        updated_at=now
                    )
                    session.add(plan_record)

                order.pro_extended_at = now
                order.status = PaymentOrderStatus.SUCCEEDED.value
                order.paid_at = now
                order.expires_at = new_expires
                order.updated_at = now

                # Audit transaction
                session.add(PaymentTransaction(
                    payment_order_id=order.id,
                    provider=order.provider,
                    provider_payment_id=order.provider_payment_id,
                    operation_type=PaymentOperationType.PAYMENT.value,
                    amount=order.amount,
                    currency=order.currency,
                    status=PaymentOrderStatus.SUCCEEDED.value,
                    provider_status=prov_res.status,
                    raw_metadata_safe="SUCCESS: Pro extended +30 days",
                    created_at=now,
                    updated_at=now
                ))

                # Auto-verify organization when PRO is activated
                org_stmt = select(Organization).where(Organization.id == order.organization_id)
                org = (await session.execute(org_stmt)).scalar_one_or_none()
                if org:
                    org.is_verified = True
                    org.updated_at = now

                logger.info(
                    "PRO ACTIVATED: Order %s extended organization %s Pro until %s (is_verified=True)",
                    order.id, order.organization_id, new_expires
                )

            # 3. Idempotent Telegram User Notification
            if order.success_notified_at is None and order.user_id:
                user_stmt = select(User).where(User.id == order.user_id)
                user = (await session.execute(user_stmt)).scalar_one_or_none()
                if user and user.telegram_id:
                    # Guarantee exp_fmt comes from OrganizationPlan.expires_at (+30 days), never order.expires_at (1h checkout TTL)
                    cur_plan_res = await session.execute(
                        select(OrganizationPlan).where(OrganizationPlan.organization_id == order.organization_id)
                    )
                    cur_plan = cur_plan_res.scalar_one_or_none()
                    effective_pro_expires = (
                        (cur_plan.expires_at if cur_plan and cur_plan.expires_at else None)
                        or (new_expires if 'new_expires' in locals() else None)
                        or (now + timedelta(days=settings.PRO_SUBSCRIPTION_DAYS))
                    )
                    exp_fmt = ensure_utc(effective_pro_expires).strftime("%d.%m.%Y")
                    msg_text = (
                        "🎉 <b>Оплата прошла успешно!</b>\n\n"
                        f"Ivently Pro активирован до <b>{exp_fmt}</b>.\n"
                        "Вам доступно до 20 маркетинговых рассылок в месяц.\n\n"
                        "Спасибо, что развиваете сообщество вместе с Ivently!"
                    )
                    reply_markup = None
                    if order.receipt_url:
                        reply_markup = {
                            "inline_keyboard": [
                                [{"text": "Электронный чек", "url": order.receipt_url}]
                            ]
                        }
                    sent = await send_telegram_notification(
                        chat_id=user.telegram_id,
                        text=msg_text,
                        reply_markup=reply_markup
                    )
                    if sent:
                        order.success_notified_at = now

            await session.commit()
            await session.refresh(order)

        elif prov_res.status == "canceled":
            if order.status != PaymentOrderStatus.SUCCEEDED.value:
                order.status = PaymentOrderStatus.CANCELED.value
                order.updated_at = now
                session.add(PaymentTransaction(
                    payment_order_id=order.id,
                    provider=order.provider,
                    provider_payment_id=order.provider_payment_id,
                    operation_type=PaymentOperationType.PAYMENT.value,
                    amount=order.amount,
                    currency=order.currency,
                    status=PaymentOrderStatus.CANCELED.value,
                    provider_status=prov_res.status,
                    raw_metadata_safe="CANCELED: User closed or cancelled checkout",
                    created_at=now,
                    updated_at=now
                ))
                await session.commit()
                await session.refresh(order)

        return order

    @classmethod
    async def handle_webhook(
        cls,
        session: AsyncSession,
        payload: Dict[str, Any],
        provider: Optional[PaymentProvider] = None
    ) -> Dict[str, Any]:
        """
        Handles incoming provider webhook notification with audit logging and replay protection.
        """
        active_provider = provider or get_payment_provider()
        parsed = active_provider.parse_webhook(payload)

        event_type = parsed.get("event_type", "unknown")
        provider_payment_id = parsed.get("provider_payment_id")
        event_id = payload.get("id") or f"{event_type}_{provider_payment_id}"

        now = utc_now()

        # Check existing webhook log for idempotency
        log_stmt = select(PaymentWebhookLog).where(
            PaymentWebhookLog.event_id == event_id,
            PaymentWebhookLog.provider == "yookassa"
        )
        existing_log = (await session.execute(log_stmt)).scalar_one_or_none()
        if existing_log and existing_log.processing_status == WebhookProcessingStatus.PROCESSED.value:
            logger.info("Webhook %s already processed, returning idempotent 200 OK", event_id)
            return {"status": "already_processed", "event_id": event_id}

        # Create or update log entry
        if not existing_log:
            webhook_log = PaymentWebhookLog(
                id=str(uuid.uuid4()),
                provider="yookassa",
                event_id=event_id,
                provider_payment_id=provider_payment_id,
                event_type=event_type,
                received_at=now,
                processing_status=WebhookProcessingStatus.RECEIVED.value,
                payload_sanitized=f"event={event_type}; payment_id={provider_payment_id}"
            )
            session.add(webhook_log)
        else:
            webhook_log = existing_log

        # Locate PaymentOrder
        order_stmt = select(PaymentOrder).where(
            PaymentOrder.provider_payment_id == provider_payment_id
        )
        order = (await session.execute(order_stmt)).scalar_one_or_none()

        if not order:
            logger.warning("Webhook received for unknown provider_payment_id: %s", provider_payment_id)
            webhook_log.processing_status = WebhookProcessingStatus.IGNORED.value
            webhook_log.error_message = f"PaymentOrder not found for provider_id {provider_payment_id}"
            webhook_log.processed_at = now
            await session.commit()
            return {"status": "order_not_found"}

        if event_type == "payment.succeeded":
            await cls.verify_and_activate_order(session, order, active_provider)
        elif event_type == "payment.canceled":
            # Verify cancellation directly with provider to prevent spoofing
            try:
                prov_res = await active_provider.get_payment(provider_payment_id)
            except Exception as e:
                logger.error("Failed to verify canceled payment with provider %s: %s", provider_payment_id, e)
                prov_res = None

            if prov_res and prov_res.status == "canceled":
                if order.status != PaymentOrderStatus.SUCCEEDED.value:
                    order.status = PaymentOrderStatus.CANCELED.value
                    order.updated_at = now
                    session.add(PaymentTransaction(
                        payment_order_id=order.id,
                        provider=order.provider,
                        provider_payment_id=provider_payment_id,
                        operation_type=PaymentOperationType.PAYMENT.value,
                        amount=order.amount,
                        currency=order.currency,
                        status=PaymentOrderStatus.CANCELED.value,
                        provider_status="canceled",
                        raw_metadata_safe="Verified Webhook: payment.canceled",
                        created_at=now,
                        updated_at=now
                    ))
            else:
                logger.warning(
                    "SECURITY: Rejecting unverified payment.canceled for order %s (provider status: %s)",
                    order.id, getattr(prov_res, "status", "unknown")
                )
        elif event_type == "refund.succeeded":
            # Verify refund with provider
            try:
                prov_res = await active_provider.get_payment(provider_payment_id)
            except Exception as e:
                logger.error("Failed to verify refund with provider %s: %s", provider_payment_id, e)
                prov_res = None

            raw_data = prov_res.raw_response if prov_res else {}
            refunded_amount = raw_data.get("refunded_amount", {}).get("value")
            is_verified_refund = bool(
                prov_res and (
                    prov_res.status in ("canceled", "refunded")
                    or (refunded_amount and float(refunded_amount) > 0)
                    or raw_data.get("cancellation_details")
                    or event_type == "refund.succeeded"
                )
            )

            if is_verified_refund:
                order.status = PaymentOrderStatus.REFUNDED.value
                order.updated_at = now
                session.add(PaymentTransaction(
                    payment_order_id=order.id,
                    provider=order.provider,
                    provider_payment_id=provider_payment_id,
                    operation_type=PaymentOperationType.REFUND.value,
                    amount=order.amount,
                    currency=order.currency,
                    status=PaymentOrderStatus.REFUNDED.value,
                    provider_status="refund.succeeded",
                    raw_metadata_safe="Verified Webhook: refund.succeeded",
                    created_at=now,
                    updated_at=now
                ))

                # Revoke Organization PRO plan on confirmed refund
                plan_stmt = select(OrganizationPlan).where(
                    OrganizationPlan.organization_id == order.organization_id
                )
                plan_record = (await session.execute(plan_stmt)).scalar_one_or_none()
                if plan_record:
                    plan_record.plan = PlanType.FREE.value
                    plan_record.status = PlanStatus.CANCELLED.value
                    plan_record.expires_at = now
                    plan_record.updated_at = now

                    # Reset verified status
                    org_stmt = select(Organization).where(Organization.id == order.organization_id)
                    org = (await session.execute(org_stmt)).scalar_one_or_none()
                    if org:
                        org.is_verified = False
                        org.updated_at = now

                    logger.warning(
                        "REVOKED PRO PLAN: Organization %s plan reverted to Free and is_verified=False due to refund on order %s",
                        order.organization_id, order.id
                    )
            else:
                logger.warning(
                    "SECURITY: Rejecting unverified refund.succeeded for order %s",
                    order.id
                )

        webhook_log.processing_status = WebhookProcessingStatus.PROCESSED.value
        webhook_log.processed_at = now
        await session.commit()

        return {"ok": True, "event": event_type, "order_id": order.id}

    @classmethod
    async def mark_receipt_issued(
        cls,
        session: AsyncSession,
        order_id: str,
        receipt_url: str
    ) -> PaymentOrder:
        """
        Admin action to link the official «Мой налог» receipt URL to a fulfilled order.
        Validates URL format and updates status to 'issued'.
        """
        clean_url = receipt_url.strip()
        if not clean_url.startswith("https://"):
            raise HTTPException(
                status_code=422,
                detail="URL чека должен начинаться с https://"
            )

        order_stmt = select(PaymentOrder).where(PaymentOrder.id == order_id)
        order = (await session.execute(order_stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

        now = utc_now()
        order.receipt_status = ReceiptStatus.ISSUED.value
        order.receipt_url = clean_url
        order.receipt_issued_at = now
        order.updated_at = now

        # If user has telegram_id, optionally notify them about their receipt
        if order.user_id:
            user_stmt = select(User).where(User.id == order.user_id)
            user = (await session.execute(user_stmt)).scalar_one_or_none()
            if user and user.telegram_id:
                await send_telegram_notification(
                    chat_id=user.telegram_id,
                    text="🧾 <b>Электронный чек по подписке Ivently Pro готов.</b>",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "Открыть чек", "url": clean_url}]
                        ]
                    }
                )

        await session.commit()
        await session.refresh(order)
        logger.info("Admin marked receipt issued for Order %s: %s", order.id, clean_url)
        return order

    @classmethod
    async def get_order_for_user(
        cls,
        session: AsyncSession,
        order_id: str,
        user: User
    ) -> PaymentOrder:
        """
        Returns order details, verifying ownership or admin rights.
        """
        order_stmt = select(PaymentOrder).where(PaymentOrder.id == order_id)
        order = (await session.execute(order_stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

        # Verify access: either user initiated the order, or user owns the organization, or admin
        if order.user_id != user.id and not settings.is_admin(user.telegram_id):
            org_stmt = select(Organization).where(Organization.id == order.organization_id)
            org = (await session.execute(org_stmt)).scalar_one_or_none()
            if not org or org.owner_user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="У вас нет доступа к этому платежу"
                )

        return order

    @classmethod
    async def get_organization_payment_history(
        cls,
        session: AsyncSession,
        organization_id: str,
        user: User
    ) -> List[PaymentOrder]:
        """
        Returns chronological payment history for an organization.
        """
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org = (await session.execute(org_stmt)).scalar_one_or_none()
        if not org or org.status == OrganizationStatus.DELETED.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")

        if org.owner_user_id != user.id and not settings.is_admin(user.telegram_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этой организации"
            )

        orders_stmt = select(PaymentOrder).where(
            PaymentOrder.organization_id == organization_id
        ).order_by(desc(PaymentOrder.created_at))

        return list((await session.execute(orders_stmt)).scalars().all())
