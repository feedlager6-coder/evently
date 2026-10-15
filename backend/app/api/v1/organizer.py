import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import json
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("evently.organizer")

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_plan import PlanType
from app.models.event import Event
from app.models.attendee import EventAttendee
from app.models.ticket_checkin import TicketCheckIn
from app.schemas.event import EventSummary
from app.schemas.audience import OrganizerAudienceResponse
from app.schemas.insights import OrganizerInsightsResponse
from app.schemas.broadcast import (
    BroadcastPreviewRequest,
    BroadcastPreviewResponse,
    BroadcastCreateRequest,
    BroadcastItem,
    BroadcastDetail,
)
from app.schemas.entitlement import (
    OrganizerEntitlementsResponse,
    CapabilityInfo,
    EntitlementLimits,
)
from app.api.deps import get_current_user
from app.services.event_service import get_organizer_events, compute_ticket_signature, build_signed_ticket_code
from app.services.audience_service import get_organizer_audience
from app.services.insights_service import get_organizer_insights
from app.services.entitlement_service import EntitlementService, CAPABILITY_REGISTRY
from app.services.broadcast_service import (
    preview_broadcast,
    create_broadcast,
    list_organizer_broadcasts,
    get_broadcast_detail,
)

router = APIRouter(prefix="/organizer", tags=["Organizer"])


@router.get("/events", response_model=List[EventSummary])
async def list_my_organized_events(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns all events created by the authenticated organizer across all moderation states:
    pending, published, rejected, and cancelled.
    """
    return await get_organizer_events(session, organizer_user_id=user.id)


@router.get("/audience", response_model=OrganizerAudienceResponse)
async def get_audience_overview(
    org_id: Optional[str] = Query(None, description="Optional organization ID to filter audience metrics"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns comprehensive, un-faked audience metrics for the authenticated organizer.
    Includes subscriber totals, 7d/30d growth, event interaction metrics, and deduplicated unique reach.
    """
    return await get_organizer_audience(session, organizer_user_id=user.id, target_org_id=org_id)


@router.get("/insights", response_model=OrganizerInsightsResponse)
async def get_my_organizer_insights(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns unified organizer insights covering audience growth, event performance totals,
    broadcast attribution totals, and discovery source breakdown.
    """
    return await get_organizer_insights(session, organizer_user_id=user.id)


@router.post("/broadcasts/preview", response_model=BroadcastPreviewResponse)
async def preview_organizer_broadcast(
    req: BroadcastPreviewRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Calculates verified audience and renders message preview without sending.
    """
    return await preview_broadcast(
        session=session,
        organizer_user_id=user.id,
        organization_id=req.organization_id,
        target_type=getattr(req.target_type, 'value', req.target_type),
        broadcast_type=getattr(req.broadcast_type, 'value', req.broadcast_type),
        template_key=getattr(req.template_key, 'value', req.template_key),
        event_id=req.event_id,
        custom_text=req.custom_text,
    )


@router.post("/broadcasts", response_model=BroadcastDetail)
async def create_organizer_broadcast(
    req: BroadcastCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Creates and dispatches an organizer broadcast campaign.
    """
    return await create_broadcast(
        session=session,
        organizer_user_id=user.id,
        req=req,
    )


@router.get("/broadcasts", response_model=List[BroadcastItem])
async def get_my_broadcasts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists all broadcast campaigns for organizations owned by the organizer.
    """
    return await list_organizer_broadcasts(session, organizer_user_id=user.id)


@router.get("/broadcasts/{broadcast_id}", response_model=BroadcastDetail)
async def get_broadcast_by_id(
    broadcast_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns detailed delivery metrics and message preview for a specific broadcast.
    """
    return await get_broadcast_detail(session, organizer_user_id=user.id, broadcast_id=broadcast_id)


@router.get("/entitlements", response_model=OrganizerEntitlementsResponse)
async def get_my_entitlements(
    org_id: Optional[str] = Query(None, description="Optional organization ID to inspect entitlements for"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns verified capability entitlements and quota limits for the organizer.
    Strictly verifies organization ownership (403 for non-owner, 404 for deleted or non-existent).
    Returns only safe public metadata; never exposes internal secrets or private user data.
    """
    target_org_id = org_id
    org_name = None

    if target_org_id:
        # Check ownership and status
        org_stmt = select(Organization).where(Organization.id == target_org_id)
        org = (await session.execute(org_stmt)).scalar_one_or_none()
        if not org or org.status == OrganizationStatus.DELETED.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
        if org.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не являетесь владельцем этой организации")
        org_name = org.name
    else:
        # Lookup first active organization owned by this user
        user_orgs_stmt = (
            select(Organization)
            .where(
                Organization.owner_user_id == user.id,
                Organization.status != OrganizationStatus.DELETED.value
            )
            .order_by(Organization.created_at.asc())
        )
        first_org = (await session.execute(user_orgs_stmt)).scalars().first()
        if first_org:
            target_org_id = first_org.id
            org_name = first_org.name

    if not target_org_id:
        # User has no organizations yet: return default Free baseline
        return OrganizerEntitlementsResponse(
            organization_id=None,
            organization_name=None,
            plan="free",
            status="active",
            starts_at=None,
            expires_at=None,
            capabilities={
                key: CapabilityInfo(
                    key=key,
                    title=defn["title"],
                    description=defn["description"],
                    status=defn["plans"]["free"],
                    is_pro_feature=defn["is_pro_feature"],
                    limit=settings.FREE_BROADCASTS_PER_MONTH if key == "broadcasts_extended" else None,
                )
                for key, defn in CAPABILITY_REGISTRY.items()
            },
            limits=EntitlementLimits(
                broadcasts_per_month=settings.FREE_BROADCASTS_PER_MONTH,
                broadcasts_used_this_month=0,
                broadcasts_remaining=settings.FREE_BROADCASTS_PER_MONTH,
            ),
        )

    if target_org_id:
        try:
            from app.services.payment_service import PaymentService
            await PaymentService.reconcile_pending_orders_for_org(session, target_org_id)
        except Exception:
            pass

    return await EntitlementService.get_entitlements(session, target_org_id, org_name=org_name)


@router.post("/organizations/{org_id}/pro", response_model=OrganizerEntitlementsResponse)
async def upgrade_organization_pro(
    org_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Activates PRO plan for an organization owned by the current user.
    Requires subscription payment when payments are enabled, unless executed by admin.
    """
    if (settings.PAYMENTS_ENABLED or settings.APP_ENV == "production") and not settings.is_admin(user.telegram_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Для подключения тарифа Pro необходимо оформить подписку"
        )

    stmt = select(Organization).where(Organization.id == org_id)
    org = (await session.execute(stmt)).scalar_one_or_none()
    if not org or org.status == OrganizationStatus.DELETED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
    if org.owner_user_id != user.id and not settings.is_admin(user.telegram_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не являетесь владельцем этой организации")

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.PRO_SUBSCRIPTION_DAYS)
    await EntitlementService.set_organization_plan(session, org_id, plan=PlanType.PRO.value, expires_at=expires_at)
    return await EntitlementService.get_entitlements(session, org_id, org_name=org.name)


class CheckInRequest(BaseModel):
    ticket_code: str


class CheckInResponse(BaseModel):
    status: str
    message: str
    ticket_code: str
    checked_in_at: str
    event_id: str
    event_title: str
    guest_name: Optional[str] = "Гость Ivently"
    is_payment_required_at_door: bool = False
    price_amount: Optional[float] = None


@router.post("/events/{event_id}/check-in", response_model=CheckInResponse)
async def check_in_event_ticket(
    event_id: str,
    req: CheckInRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Validates and performs persistent check-in for a ticket code or QR payload for the organizer's event.
    """
    stmt = select(Event).where(Event.id == event_id)
    event = (await session.execute(stmt)).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено")

    # Authorize: user must be the organizer or admin
    is_author = (event.organizer_user_id == user.id)
    is_admin = settings.is_admin(user.telegram_id)
    if not is_author and not is_admin:
        if event.organization_id:
            org_stmt = select(Organization).where(Organization.id == event.organization_id)
            org = (await session.execute(org_stmt)).scalar_one_or_none()
            if not org or org.owner_user_id != user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У вас нет прав администратора для этого события")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У вас нет прав администратора для этого события")

    raw_code = req.ticket_code.strip()
    ticket_id = raw_code
    payload_event_id = None
    provided_sig = None
    guest_name = "Гость Ivently"
    candidate_user_ident = None

    if raw_code.startswith("{") and raw_code.endswith("}"):
        try:
            parsed = json.loads(raw_code)
            ticket_id = (parsed.get("ticket_id") or raw_code).strip()
            payload_event_id = parsed.get("event_id")
            if parsed.get("sig"):
                provided_sig = str(parsed.get("sig")).strip().upper()
            if parsed.get("telegram_id"):
                candidate_user_ident = str(parsed.get("telegram_id")).strip()
            elif parsed.get("user_id"):
                candidate_user_ident = str(parsed.get("user_id")).strip()
            if parsed.get("guest_name"):
                guest_name = parsed.get("guest_name")

            if ticket_id.startswith("IVN-"):
                t_parts = ticket_id.split("-")
                if len(t_parts) == 4 and not provided_sig:
                    candidate_user_ident = candidate_user_ident or t_parts[2].strip()
                    provided_sig = t_parts[3].strip().upper()
        except Exception:
            pass
    elif ticket_id.startswith("rsvp_"):
        parts = ticket_id.split("_")
        if len(parts) >= 3:
            payload_event_id = parts[1]
            candidate_user_ident = parts[2].strip()
    elif ticket_id.startswith("IVN-"):
        parts = ticket_id.split("-")
        if len(parts) == 4 and parts[2].isdigit():
            candidate_user_ident = parts[2].strip()
            provided_sig = parts[3].strip().upper()
        elif len(parts) >= 3 and parts[-1].isdigit():
            candidate_user_ident = parts[-1].strip()

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.strftime("%H:%M:%S")

    # Payment at door check (C7)
    is_free = bool(getattr(event, "is_free", False)) or (event.price_amount is not None and event.price_amount == 0)
    ticket_url = getattr(event, "source_url", None) or getattr(event, "registration_url", None) or getattr(event, "ticket_link", None)
    is_payment_required_at_door = not is_free and not ticket_url and (event.price_amount is not None and event.price_amount > 0)
    price_amount = float(event.price_amount) if (event.price_amount is not None and event.price_amount > 0) else None

    # 1. Check event mismatch
    if payload_event_id and payload_event_id != event_id:
        return CheckInResponse(
            status="invalid",
            message="Билет относится к другому мероприятию",
            ticket_code=ticket_id,
            checked_in_at=now_iso,
            event_id=event_id,
            event_title=event.title,
            guest_name=guest_name,
            is_payment_required_at_door=is_payment_required_at_door,
            price_amount=price_amount,
        )

    # 2. Validate attendee registration in EventAttendee and compute canonical attendee code
    canonical_attendee_code = None
    if candidate_user_ident and candidate_user_ident.isdigit():
        ident_num = int(candidate_user_ident)
        target_user = (await session.execute(
            select(User).where(or_(User.id == ident_num, User.telegram_id == ident_num))
        )).scalar_one_or_none()
        if target_user:
            att = (await session.execute(
                select(EventAttendee).where(
                    EventAttendee.event_id == event_id,
                    EventAttendee.user_id == target_user.id
                )
            )).scalar_one_or_none()
            if att:
                # Cryptographic signature validation
                expected_sig = compute_ticket_signature(event_id, target_user.id)
                expected_tg_sig = compute_ticket_signature(event_id, target_user.telegram_id) if target_user.telegram_id else None

                if provided_sig:
                    if provided_sig != expected_sig and provided_sig != expected_tg_sig:
                        return CheckInResponse(
                            status="invalid",
                            message="Недействительная подпись билета",
                            ticket_code=ticket_id,
                            checked_in_at=now_iso,
                            event_id=event_id,
                            event_title=event.title,
                            guest_name=guest_name,
                            is_payment_required_at_door=is_payment_required_at_door,
                            price_amount=price_amount,
                        )
                elif settings.APP_ENV == "production":
                    # In production, signature is mandatory to prevent user_id enumeration attacks
                    return CheckInResponse(
                        status="invalid",
                        message="Билет требует криптографической подписи",
                        ticket_code=ticket_id,
                        checked_in_at=now_iso,
                        event_id=event_id,
                        event_title=event.title,
                        guest_name=guest_name,
                        is_payment_required_at_door=is_payment_required_at_door,
                        price_amount=price_amount,
                    )

                user_name = f"{target_user.first_name or ''} {target_user.last_name or ''}".strip()
                guest_name = user_name or target_user.username or guest_name
                canonical_attendee_code = f"attendee:{target_user.id}"
            elif not is_payment_required_at_door and not ticket_url:
                # User exists in platform but did not register for this event
                return CheckInResponse(
                    status="invalid",
                    message="Билет не найден среди регистраций на это мероприятие",
                    ticket_code=ticket_id,
                    checked_in_at=now_iso,
                    event_id=event_id,
                    event_title=event.title,
                    guest_name=guest_name,
                    is_payment_required_at_door=is_payment_required_at_door,
                    price_amount=price_amount,
                )

    # 3. Check for completely fake strings (not matching any valid ticket pattern)
    if not canonical_attendee_code and not is_payment_required_at_door and not ticket_url:
        if not ticket_id.startswith("IVN-") and not ticket_id.startswith("rsvp_"):
            return CheckInResponse(
                status="invalid",
                message="Недействительный QR-код или неизвестный билет",
                ticket_code=ticket_id,
                checked_in_at=now_iso,
                event_id=event_id,
                event_title=event.title,
                guest_name=guest_name,
                is_payment_required_at_door=is_payment_required_at_door,
                price_amount=price_amount,
            )

    # 4. Check if ticket or canonical attendee code has already been checked in
    codes_to_check = [ticket_id]
    if canonical_attendee_code and canonical_attendee_code != ticket_id:
        codes_to_check.append(canonical_attendee_code)

    existing_stmt = select(TicketCheckIn).where(
        TicketCheckIn.event_id == event_id,
        TicketCheckIn.ticket_code.in_(codes_to_check)
    )
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing:
        prev_time = existing.created_at.strftime("%H:%M:%S") if existing.created_at else now_iso
        return CheckInResponse(
            status="already_checked_in",
            message=f"Билет уже был использован ранее в {prev_time}",
            ticket_code=ticket_id,
            checked_in_at=prev_time,
            event_id=event_id,
            event_title=event.title,
            guest_name=existing.guest_name or guest_name,
            is_payment_required_at_door=is_payment_required_at_door,
            price_amount=price_amount,
        )

    # 5. Insert new check-in record and canonical check-in record with atomic unique constraint error handling
    new_checkin = TicketCheckIn(
        event_id=event_id,
        ticket_code=ticket_id,
        checked_in_by_user_id=user.id,
        guest_name=guest_name,
        created_at=now_utc,
    )
    session.add(new_checkin)
    if canonical_attendee_code and canonical_attendee_code != ticket_id:
        canonical_checkin = TicketCheckIn(
            event_id=event_id,
            ticket_code=canonical_attendee_code,
            checked_in_by_user_id=user.id,
            guest_name=guest_name,
            created_at=now_utc,
        )
        session.add(canonical_checkin)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = (await session.execute(existing_stmt)).scalars().first()
        prev_time = existing.created_at.strftime("%H:%M:%S") if (existing and existing.created_at) else now_iso
        return CheckInResponse(
            status="already_checked_in",
            message=f"Билет уже был использован ранее в {prev_time}",
            ticket_code=ticket_id,
            checked_in_at=prev_time,
            event_id=event_id,
            event_title=event.title,
            guest_name=guest_name,
            is_payment_required_at_door=is_payment_required_at_door,
            price_amount=price_amount,
        )

    success_msg = "Билет действителен. Вход подтвержден!"
    if is_payment_required_at_door:
        formatted_price = int(price_amount) if price_amount and price_amount.is_integer() else price_amount
        success_msg = f"Билет действителен. ОПЛАТА НА ВХОДЕ: {formatted_price} ₽"

    return CheckInResponse(
        status="success",
        message=success_msg,
        ticket_code=ticket_id,
        checked_in_at=now_iso,
        event_id=event_id,
        event_title=event.title,
        guest_name=guest_name,
        is_payment_required_at_door=is_payment_required_at_door,
        price_amount=price_amount,
    )


@router.get("/events/{event_id}/attendees/export")
async def export_event_attendees(
    event_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    send_to_telegram: bool = Query(True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Exports registered attendees and their door check-in statuses for a specific event.
    Authorized for the event creator, organization owner, or admin.
    Returns structured JSON or downloadable UTF-8 CSV with BOM for Excel compatibility.
    When send_to_telegram=True and user has telegram_id, delivers the CSV directly to their Telegram bot chat.
    """
    event = await session.get(Event, event_id)
    if not event or event.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Событие не найдено")

    is_admin_user = settings.is_admin(user.telegram_id)
    is_creator = event.organizer_user_id == user.id

    is_org_owner = False
    if event.organization_id:
        org = await session.get(Organization, event.organization_id)
        if org and org.owner_user_id == user.id:
            is_org_owner = True

    if not (is_admin_user or is_creator or is_org_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет прав на экспорт списка гостей этого события"
        )

    # Query all attendees joining User
    stmt = (
        select(EventAttendee, User)
        .join(User, EventAttendee.user_id == User.id)
        .where(EventAttendee.event_id == event_id)
        .order_by(EventAttendee.created_at.asc())
    )
    rows = (await session.execute(stmt)).all()

    # Query all check-ins for this event
    checkin_stmt = select(TicketCheckIn).where(TicketCheckIn.event_id == event_id)
    checkins = (await session.execute(checkin_stmt)).scalars().all()
    checkin_map = {ci.ticket_code: ci for ci in checkins}

    attendees_list = []
    checked_in_count = 0

    for idx, (attendee, guest_user) in enumerate(rows, start=1):
        guest_name = f"{guest_user.first_name or ''} {guest_user.last_name or ''}".strip() or "Гость"
        username_str = f"@{guest_user.username}" if guest_user.username else "—"
        ticket_code = attendee.ticket_code or build_signed_ticket_code(event_id, guest_user.id)
        reg_date_str = attendee.created_at.strftime("%d.%m.%Y %H:%M") if attendee.created_at else "—"

        is_checked_in = False
        checkin_time_str = "—"
        if ticket_code in checkin_map:
            is_checked_in = True
            ci_time = checkin_map[ticket_code].created_at
            checkin_time_str = ci_time.strftime("%d.%m.%Y %H:%M:%S") if ci_time else "Да"
            checked_in_count += 1

        checkin_status_str = "Прошел чек-ин" if is_checked_in else "Ожидается"

        attendees_list.append({
            "index": idx,
            "user_id": guest_user.id,
            "guest_name": guest_name,
            "username": username_str,
            "ticket_code": ticket_code,
            "registered_at": reg_date_str,
            "is_checked_in": is_checked_in,
            "checkin_status": checkin_status_str,
            "checkin_time": checkin_time_str,
        })

    if format == "csv":
        import csv
        import io
        import httpx
        output = io.StringIO()
        # UTF-8 BOM so Excel opens Cyrillic without garbled text
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["№", "Имя гостя", "Telegram", "Код билета", "Дата регистрации", "Статус прохода", "Время чек-ина"])
        for item in attendees_list:
            writer.writerow([
                item["index"],
                item["guest_name"],
                item["username"],
                item["ticket_code"],
                item["registered_at"],
                item["checkin_status"],
                item["checkin_time"],
            ])
        csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")
        filename = f"attendees_{event_id[:8]}.csv"

        # Direct delivery to organizer's Telegram chat if requested and user has Telegram ID
        if send_to_telegram and user.telegram_id and settings.is_live_bot:
            try:
                bot_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendDocument"
                safe_title = event.title or "Событие"
                caption = f"📋 Список гостей: {safe_title}\nВсего гостей: {len(attendees_list)}\nПрошли чек-ин: {checked_in_count}"
                async with httpx.AsyncClient(timeout=10.0) as bot_client:
                    files = {
                        "document": (filename, csv_bytes, "text/csv")
                    }
                    data = {
                        "chat_id": str(user.telegram_id),
                        "caption": caption
                    }
                    resp = await bot_client.post(bot_url, data=data, files=files)
                    if resp.status_code != 200:
                        logger.warning("Telegram sendDocument failed: %s %s", resp.status_code, resp.text)
                    else:
                        logger.info("Successfully sent attendee CSV for event %s to user telegram %s", event_id, user.telegram_id)
            except Exception as e:
                logger.error("Error sending attendee CSV to telegram chat: %s", e)

        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    return {
        "event_id": event_id,
        "event_title": event.title,
        "total_attendees": len(attendees_list),
        "checked_in_count": checked_in_count,
        "attendees": attendees_list,
    }



