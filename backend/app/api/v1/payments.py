import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.payment import PaymentOrder, ReceiptStatus
from app.schemas.payment import (
    CreatePaymentOrderRequest,
    PaymentOrderResponse,
    PaymentConfigResponse,
    MarkReceiptRequest,
)
from app.api.deps import get_current_user, require_admin
from app.services.payment_service import PaymentService, get_payment_provider

logger = logging.getLogger("evently.api.payments")

router = APIRouter(tags=["Payments"])


# --- Public / Meta ---

@router.get("/meta/payment-config", response_model=PaymentConfigResponse)
async def get_payment_config():
    """
    Returns public payment system parameters (price, period, enabled status)
    so frontend never hardcodes prices.
    """
    return PaymentConfigResponse(
        payments_enabled=settings.PAYMENTS_ENABLED,
        pro_monthly_price_rub=float(settings.PRO_MONTHLY_PRICE_RUB),
        pro_days=settings.PRO_SUBSCRIPTION_DAYS
    )


# --- Organizer Endpoints ---

@router.post("/organizer/payments/pro", response_model=PaymentOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_pro_payment(
    req: CreatePaymentOrderRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Creates an Ivently Pro purchase order and initiates checkout with YooKassa.
    Returns order details including hosted checkout confirmation URL.
    """
    order, _ = await PaymentService.create_pro_order(
        session=session,
        organization_id=req.organization_id,
        user=user,
        customer_email=req.customer_email
    )
    return order


@router.get("/organizer/payments/{order_id}", response_model=PaymentOrderResponse)
async def get_payment_order_status(
    order_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns verified status of a payment order.
    If the order is still pending/waiting, performs server-side reconciliation
    with the provider to ensure immediate fulfillment on user return.
    """
    order = await PaymentService.get_order_for_user(session, order_id, user)

    # If pending or waiting for payment, reconcile with provider
    if order.status in ("pending", "waiting_for_payment"):
        try:
            order = await PaymentService.verify_and_activate_order(session, order)
        except Exception as e:
            logger.warning("Reconciliation on status polling failed for order %s: %s", order.id, e)

    return order


@router.get("/organizer/payments", response_model=List[PaymentOrderResponse])
async def get_my_organization_payments(
    org_id: str = Query(..., description="Organization UUID to inspect payments for"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns chronological payment history for an organization owned by the user.
    """
    return await PaymentService.get_organization_payment_history(session, org_id, user)


# --- Webhook Endpoint ---

@router.post("/payments/webhook/yookassa")
async def yookassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Inbound webhook notification handler for YooKassa events (payment.succeeded, etc.).
    Always responds with 200 OK after logging and processing.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.warning("Malformed JSON in YooKassa webhook: %s", e)
        return {"status": "invalid_json"}

    return await PaymentService.handle_webhook(session, payload)


# --- Admin Endpoints ---

@router.get("/admin/payments", response_model=List[PaymentOrderResponse])
async def list_admin_payments(
    receipt_status: Optional[str] = Query(None, description="Filter by receipt status: pending, issued"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Admin overview of recent payment orders and pending receipt tasks.
    """
    stmt = select(PaymentOrder).order_by(desc(PaymentOrder.created_at)).limit(limit)
    if receipt_status:
        stmt = stmt.where(PaymentOrder.receipt_status == receipt_status)

    return list((await session.execute(stmt)).scalars().all())


@router.post("/admin/payments/{order_id}/receipt", response_model=PaymentOrderResponse)
async def admin_mark_receipt_issued(
    order_id: str,
    req: MarkReceiptRequest,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Admin marks a payment's «Мой налог» receipt as issued and links the official HTTPS URL.
    """
    return await PaymentService.mark_receipt_issued(session, order_id, req.receipt_url)


@router.post("/admin/payments/{order_id}/reconcile", response_model=PaymentOrderResponse)
async def admin_reconcile_payment(
    order_id: str,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Admin triggers manual server-side reconciliation of an order with YooKassa.
    """
    order_stmt = select(PaymentOrder).where(PaymentOrder.id == order_id)
    order = (await session.execute(order_stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    return await PaymentService.verify_and_activate_order(session, order)
