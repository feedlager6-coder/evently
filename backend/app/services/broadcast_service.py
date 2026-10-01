import asyncio
import html
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case

from app.config import settings
from app.models.organization import Organization, OrganizationStatus
from app.models.event import Event
from app.models.user import User
from app.models.subscription import Subscription
from app.models.interest import EventInterest
from app.models.attendee import EventAttendee
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastTargetType,
    BroadcastType,
    BroadcastTemplateKey,
    BroadcastStatus,
    RecipientStatus,
)
from app.schemas.broadcast import (
    BroadcastPreviewResponse,
    BroadcastCreateRequest,
    BroadcastItem,
    BroadcastDetail,
)

logger = logging.getLogger("evently.broadcasts")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_broadcast_content(
    organization: Organization,
    template_key: str,
    event: Optional[Event] = None,
    custom_text: Optional[str] = None,
    broadcast_id: Optional[str] = None,
    attribution_token: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Renders message HTML, button text, and deep-link URL.
    Strictly escapes all user-supplied content using html.escape to guarantee
    safe Telegram HTML formatting without injection or parse errors.
    """
    safe_org_name = html.escape(organization.name)
    safe_custom = html.escape(custom_text.strip()) if custom_text and custom_text.strip() else ""

    if template_key == BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value:
        if not event:
            raise HTTPException(status_code=400, detail="Для анонса события необходимо указать мероприятие")
        safe_title = html.escape(event.title)
        safe_venue = html.escape(event.venue_name)
        date_str = event.start_at.strftime("%d.%m.%Y в %H:%M")

        text = (
            f"🔔 <b>Новое событие от {safe_org_name}</b>\n\n"
            f"🧭 <b>{safe_title}</b>\n"
            f"📅 {date_str}\n"
            f"📍 {safe_venue}\n"
        )
        if safe_custom:
            text += f"\n💬 {safe_custom}\n"

        button_text = "Открыть событие 🧭"
        button_url = settings.get_event_deep_link(event.id, attribution_token=attribution_token)

    elif template_key == BroadcastTemplateKey.EVENT_UPDATE.value:
        if not event:
            raise HTTPException(status_code=400, detail="Для обновления события необходимо указать мероприятие")
        safe_title = html.escape(event.title)
        safe_venue = html.escape(event.venue_name)
        date_str = event.start_at.strftime("%d.%m.%Y в %H:%M")

        text = (
            f"📢 <b>Обновление события от {safe_org_name}</b>\n\n"
            f"🧭 <b>{safe_title}</b>\n"
            f"📅 {date_str}\n"
            f"📍 {safe_venue}\n"
        )
        if safe_custom:
            text += f"\n💬 {safe_custom}\n"

        button_text = "Подробнее о событии 🧭"
        button_url = settings.get_event_deep_link(event.id, attribution_token=attribution_token)

    elif template_key == BroadcastTemplateKey.CUSTOM_UPDATE.value:
        text = (
            f"🏛 <b>Новости от {safe_org_name}</b>\n\n"
            f"💬 {safe_custom or 'Свежие обновления для подписчиков'}\n"
        )
        button_text = "Открыть профиль 🏛"
        button_url = settings.get_organization_deep_link(organization.id)
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестный шаблон рассылки: {template_key}")

    return text, button_text, button_url


async def calculate_audience(
    session: AsyncSession,
    organizer_user_id: int,
    organization_id: str,
    target_type: str,
    broadcast_type: str,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes verified audience metrics and eligible recipient user IDs according to strict rules:
    1. Primary audience: Organization subscribers with notifications_enabled == True.
    2. Contextual audience: Users who expressed interest in a specific event of the organization.
    3. Forbidden audiences: (event viewers, arbitrary users, un-subscribed past attendees) rejected.
    4. Anti-fatigue rule: Users receiving a marketing broadcast in the last 24h are excluded (marketing only).
    """
    # 1. Verify organization ownership
    org_res = await session.execute(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.status != OrganizationStatus.DELETED.value
        )
    )
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    if org.owner_user_id != organizer_user_id:
        raise HTTPException(status_code=403, detail="У вас нет прав для управления этой организацией")

    # 2. Validate target_type
    allowed_targets = [
        BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        BroadcastTargetType.EVENT_INTEREST.value,
    ]
    if target_type not in allowed_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый тип аудитории '{target_type}'. Допустимы только 'organization_subscribers' и 'event_interest'."
        )

    event: Optional[Event] = None
    if event_id:
        ev_res = await session.execute(
            select(Event).where(Event.id == event_id)
        )
        event = ev_res.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Событие не найдено")
        if event.organization_id != organization_id:
            raise HTTPException(
                status_code=400,
                detail="Событие не принадлежит указанной организации"
            )

    if target_type == BroadcastTargetType.EVENT_INTEREST.value and not event_id:
        raise HTTPException(
            status_code=400,
            detail="Для аудитории с интересом к событию необходимо указать event_id"
        )

    # 3. Query base audience
    if target_type == BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value:
        # Query all subscribers
        sub_stmt = (
            select(Subscription.user_id, Subscription.notifications_enabled, User.telegram_id)
            .join(User, Subscription.user_id == User.id)
            .where(Subscription.organization_id == organization_id)
        )
        sub_rows = (await session.execute(sub_stmt)).all()

        total_audience = len(sub_rows)
        disabled_notifications_count = sum(1 for row in sub_rows if not row.notifications_enabled)
        
        # Candidate users: active notifications & has telegram_id
        candidate_user_ids = [
            row.user_id for row in sub_rows
            if row.notifications_enabled and row.telegram_id is not None
        ]

    else:  # EVENT_INTEREST
        interest_stmt = (
            select(EventInterest.user_id, User.telegram_id)
            .join(User, EventInterest.user_id == User.id)
            .where(EventInterest.event_id == event_id)
        )
        interest_rows = (await session.execute(interest_stmt)).all()
        total_audience = len(interest_rows)

        # Check if any interest users have an explicit subscription with notifications_enabled=False
        interest_user_ids = [r.user_id for r in interest_rows if r.telegram_id is not None]
        if interest_user_ids:
            disabled_stmt = (
                select(Subscription.user_id)
                .where(
                    Subscription.organization_id == organization_id,
                    Subscription.user_id.in_(interest_user_ids),
                    Subscription.notifications_enabled == False
                )
            )
            disabled_user_ids = set((await session.execute(disabled_stmt)).scalars().all())
        else:
            disabled_user_ids = set()

        disabled_notifications_count = len(disabled_user_ids)
        candidate_user_ids = [
            uid for uid in interest_user_ids if uid not in disabled_user_ids
        ]

    # 4. Anti-fatigue check (rolling 24 hours) - applies only to MARKETING broadcasts
    fatigued_recipients_count = 0
    eligible_user_ids: List[int] = candidate_user_ids

    if broadcast_type == BroadcastType.MARKETING.value and candidate_user_ids:
        fatigue_cutoff = utc_now() - timedelta(hours=settings.BROADCAST_FATIGUE_HOURS)
        fatigue_stmt = (
            select(BroadcastRecipient.user_id)
            .join(Broadcast, BroadcastRecipient.broadcast_id == Broadcast.id)
            .where(
                Broadcast.broadcast_type == BroadcastType.MARKETING.value,
                BroadcastRecipient.user_id.in_(candidate_user_ids),
                BroadcastRecipient.status == RecipientStatus.SENT.value,
                BroadcastRecipient.sent_at >= fatigue_cutoff
            )
            .distinct()
        )
        fatigued_ids = set((await session.execute(fatigue_stmt)).scalars().all())
        fatigued_recipients_count = len(fatigued_ids)
        eligible_user_ids = [uid for uid in candidate_user_ids if uid not in fatigued_ids]

    return {
        "organization": org,
        "event": event,
        "total_audience": total_audience,
        "eligible_user_ids": eligible_user_ids,
        "disabled_notifications_count": disabled_notifications_count,
        "fatigued_recipients_count": fatigued_recipients_count,
    }


async def preview_broadcast(
    session: AsyncSession,
    organizer_user_id: int,
    organization_id: str,
    target_type: str,
    broadcast_type: str,
    template_key: str,
    event_id: Optional[str] = None,
    custom_text: Optional[str] = None
) -> BroadcastPreviewResponse:
    """
    Calculates audience preview and renders formatted message preview without persisting anything.
    """
    if broadcast_type == BroadcastType.TRANSACTIONAL.value:
        raise HTTPException(
            status_code=400,
            detail="Сервисные уведомления об изменениях событий отправляются системой автоматически при обновлении события. Для ручных рассылок используйте анонсы или новости организации."
        )

    if target_type == BroadcastTargetType.EVENT_INTEREST.value and template_key == BroadcastTemplateKey.CUSTOM_UPDATE.value:
        raise HTTPException(
            status_code=400,
            detail="Для аудитории с интересом к событию шаблон 'custom_update' (новости организации) недопустим. Рассылка должна быть связана с событием."
        )

    calc = await calculate_audience(
        session=session,
        organizer_user_id=organizer_user_id,
        organization_id=organization_id,
        target_type=target_type,
        broadcast_type=broadcast_type,
        event_id=event_id,
    )

    org: Organization = calc["organization"]
    event: Optional[Event] = calc["event"]

    message_text, button_text, button_url = format_broadcast_content(
        organization=org,
        template_key=template_key,
        event=event,
        custom_text=custom_text,
    )

    return BroadcastPreviewResponse(
        organization_id=org.id,
        organization_name=org.name,
        target_type=target_type,
        broadcast_type=broadcast_type,
        template_key=template_key,
        event_id=event.id if event else None,
        event_title=event.title if event else None,
        total_audience=calc["total_audience"],
        eligible_recipients=len(calc["eligible_user_ids"]),
        disabled_notifications_count=calc["disabled_notifications_count"],
        fatigued_recipients_count=calc["fatigued_recipients_count"],
        preview_text=message_text,
        preview_button_text=button_text,
        preview_button_url=button_url,
    )


async def create_broadcast(
    session: AsyncSession,
    organizer_user_id: int,
    req: BroadcastCreateRequest,
    http_client: Optional[httpx.AsyncClient] = None
) -> BroadcastDetail:
    """
    Creates broadcast record, registers idempotent recipients, and triggers dispatch.
    """
    target_type_val = getattr(req.target_type, 'value', req.target_type)
    broadcast_type_val = getattr(req.broadcast_type, 'value', req.broadcast_type)
    template_key_val = getattr(req.template_key, 'value', req.template_key)

    if broadcast_type_val == BroadcastType.TRANSACTIONAL.value:
        raise HTTPException(
            status_code=400,
            detail="Сервисные уведомления об изменениях событий отправляются системой автоматически при обновлении события. Для ручных рассылок используйте анонсы или новости организации."
        )

    if target_type_val == BroadcastTargetType.EVENT_INTEREST.value and template_key_val == BroadcastTemplateKey.CUSTOM_UPDATE.value:
        raise HTTPException(
            status_code=400,
            detail="Для аудитории с интересом к событию шаблон 'custom_update' (новости организации) недопустим. Рассылка должна быть связана с событием."
        )

    # Enforce Pro entitlement for manual broadcasts
    from app.services.entitlement_service import EntitlementService
    await EntitlementService.require_entitlement(session, req.organization_id, "broadcasts_extended")
    await EntitlementService.enforce_broadcast_capacity(session, req.organization_id, broadcast_type=broadcast_type_val)

    calc = await calculate_audience(
        session=session,
        organizer_user_id=organizer_user_id,
        organization_id=req.organization_id,
        target_type=target_type_val,
        broadcast_type=broadcast_type_val,
        event_id=req.event_id,
    )

    eligible_user_ids = calc["eligible_user_ids"]
    if len(eligible_user_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="Нет доступных получателей для отправки рассылки"
        )

    org: Organization = calc["organization"]
    event: Optional[Event] = calc["event"]

    # Create Broadcast entity
    attribution_token = secrets.token_hex(8)
    broadcast = Broadcast(
        organization_id=org.id,
        created_by_user_id=organizer_user_id,
        event_id=event.id if event else None,
        target_type=target_type_val,
        broadcast_type=broadcast_type_val,
        template_key=template_key_val,
        custom_text=req.custom_text.strip() if req.custom_text else None,
        status=BroadcastStatus.QUEUED.value,
        attribution_token=attribution_token,
        total_recipients=len(eligible_user_ids),
        sent_count=0,
        delivered_count=0,
        failed_count=0,
        blocked_count=0,
        created_at=utc_now(),
    )
    session.add(broadcast)
    await session.flush()  # generates broadcast.id

    # Add recipients idempotently
    for uid in eligible_user_ids:
        rec = BroadcastRecipient(
            broadcast_id=broadcast.id,
            user_id=uid,
            status=RecipientStatus.PENDING.value,
        )
        session.add(rec)

    await session.commit()
    await session.refresh(broadcast)

    # Immediately execute dispatch
    await dispatch_broadcast(session, broadcast.id, http_client=http_client)
    await session.refresh(broadcast)

    message_text, button_text, button_url = format_broadcast_content(
        organization=org,
        template_key=broadcast.template_key,
        event=event,
        custom_text=broadcast.custom_text,
        broadcast_id=broadcast.id,
        attribution_token=broadcast.attribution_token,
    )

    return BroadcastDetail(
        id=broadcast.id,
        organization_id=org.id,
        organization_name=org.name,
        event_id=event.id if event else None,
        event_title=event.title if event else None,
        target_type=broadcast.target_type,
        broadcast_type=broadcast.broadcast_type,
        template_key=broadcast.template_key,
        custom_text=broadcast.custom_text,
        status=broadcast.status,
        total_recipients=broadcast.total_recipients,
        sent_count=broadcast.sent_count,
        delivered_count=broadcast.delivered_count,
        failed_count=broadcast.failed_count,
        blocked_count=broadcast.blocked_count,
        opened_count=0,
        interest_count=0,
        rsvp_count=0,
        open_rate=0.0,
        interest_conversion=0.0,
        rsvp_conversion=0.0,
        created_at=broadcast.created_at,
        started_at=broadcast.started_at,
        completed_at=broadcast.completed_at,
        message_text=message_text,
        button_text=button_text,
        button_url=button_url,
        attribution_token=broadcast.attribution_token,
    )


async def dispatch_broadcast(
    session: AsyncSession,
    broadcast_id: str,
    http_client: Optional[httpx.AsyncClient] = None
) -> Broadcast:
    """
    Executes message delivery with rate limiting, 429 retry-after handling,
    and 403 Forbidden handling (setting Subscription.notifications_enabled = False).
    Guarantees idempotency by processing only PENDING recipients.
    """
    stmt = (
        select(Broadcast)
        .where(Broadcast.id == broadcast_id)
    )
    res = await session.execute(stmt)
    broadcast = res.scalar_one_or_none()
    if not broadcast:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    if broadcast.status in (BroadcastStatus.COMPLETED.value, BroadcastStatus.CANCELLED.value):
        return broadcast

    broadcast.status = BroadcastStatus.PROCESSING.value
    if not broadcast.started_at:
        broadcast.started_at = utc_now()
    if not broadcast.attribution_token:
        broadcast.attribution_token = secrets.token_hex(8)
    await session.commit()

    # Load organization and event
    org_res = await session.execute(select(Organization).where(Organization.id == broadcast.organization_id))
    org = org_res.scalar_one()

    event = None
    if broadcast.event_id:
        ev_res = await session.execute(select(Event).where(Event.id == broadcast.event_id))
        event = ev_res.scalar_one_or_none()

    message_text, button_text, button_url = format_broadcast_content(
        organization=org,
        template_key=broadcast.template_key,
        event=event,
        custom_text=broadcast.custom_text,
        broadcast_id=broadcast.id,
        attribution_token=broadcast.attribution_token,
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": button_text,
                    "url": button_url,
                    "style": "primary"
                }
            ]
        ]
    }

    # Query pending recipients with Telegram IDs
    recipients_stmt = (
        select(BroadcastRecipient, User.telegram_id)
        .join(User, BroadcastRecipient.user_id == User.id)
        .where(
            BroadcastRecipient.broadcast_id == broadcast.id,
            BroadcastRecipient.status == RecipientStatus.PENDING.value
        )
    )
    recipients_rows = (await session.execute(recipients_stmt)).all()

    # If simulation mode (not live bot and no mocked client provided)
    if not settings.is_live_bot and http_client is None:
        logger.info(f"[Test/Dev Mode] Simulating broadcast {broadcast.id} to {len(recipients_rows)} recipients")
        for rec, tg_id in recipients_rows:
            rec.status = RecipientStatus.SENT.value
            rec.sent_at = utc_now()
            broadcast.sent_count += 1
            broadcast.delivered_count += 1

        broadcast.status = BroadcastStatus.COMPLETED.value
        broadcast.completed_at = utc_now()
        await session.commit()
        return broadcast

    # Live or mocked HTTP delivery
    bot_token = settings.clean_bot_token
    rate_limit = max(1, settings.BROADCAST_RATE_LIMIT_PER_SEC)
    delay_between_messages = 1.0 / rate_limit

    async def _send_to_recipient(client: httpx.AsyncClient, rec: BroadcastRecipient, tg_id: Optional[int]):
        if not tg_id:
            rec.status = RecipientStatus.FAILED.value
            rec.error_code = "missing_telegram_id"
            rec.error_message = "User has no telegram_id"
            broadcast.failed_count += 1
            return

        cover_image_url = None
        if event and event.cover_image_url:
            from app.services.notification_service import resolve_event_cover_url
            cover_image_url = resolve_event_cover_url(event.cover_image_url)

        payload = {
            "chat_id": tg_id,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        try:
            resp = None
            if cover_image_url:
                photo_payload = {
                    "chat_id": tg_id,
                    "photo": cover_image_url,
                    "caption": message_text,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup
                }
                photo_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                try:
                    resp = await client.post(photo_url, json=photo_payload, timeout=5.0)
                    if resp.status_code == 429:
                        retry_after = 1
                        try:
                            data = resp.json()
                            if asyncio.iscoroutine(data):
                                data = await data
                            retry_after = data.get("parameters", {}).get("retry_after", 1)
                        except Exception:
                            pass
                        await asyncio.sleep(retry_after)
                        resp = await client.post(photo_url, json=photo_payload, timeout=5.0)
                    if resp.status_code != 200 and resp.status_code != 403:
                        # photo delivery error (e.g. invalid URL) -> fallback to sendMessage
                        logger.warning(f"sendPhoto failed ({resp.status_code}), falling back to sendMessage for recipient {rec.user_id}")
                        resp = None
                except Exception as photo_err:
                    logger.warning(f"sendPhoto exception, falling back to sendMessage: {photo_err}")
                    resp = None

            if resp is None:
                resp = await client.post(url, json=payload, timeout=5.0)

            # Handle 429 Too Many Requests
            if resp.status_code == 429:
                retry_after = 1
                try:
                    data = resp.json()
                    if asyncio.iscoroutine(data):
                        data = await data
                    retry_after = data.get("parameters", {}).get("retry_after", 1)
                except Exception:
                    pass
                logger.warning(f"Telegram 429 for recipient {rec.user_id}. Waiting {retry_after}s to retry...")
                await asyncio.sleep(retry_after)
                resp = await client.post(url, json=payload, timeout=5.0)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if asyncio.iscoroutine(data):
                        data = await data
                except Exception:
                    data = {}
                msg_id = data.get("result", {}).get("message_id") if isinstance(data, dict) else None
                rec.status = RecipientStatus.SENT.value
                rec.telegram_message_id = msg_id
                rec.sent_at = utc_now()
                broadcast.sent_count += 1
                broadcast.delivered_count += 1

            elif resp.status_code == 403:
                # User blocked the bot
                rec.status = RecipientStatus.BLOCKED.value
                rec.error_code = "403"
                rec.error_message = resp.text
                broadcast.blocked_count += 1

                # Disable notification subscription for this organization
                sub_stmt = (
                    select(Subscription)
                    .where(
                        Subscription.user_id == rec.user_id,
                        Subscription.organization_id == broadcast.organization_id
                    )
                )
                sub_res = await session.execute(sub_stmt)
                sub = sub_res.scalar_one_or_none()
                if sub:
                    sub.notifications_enabled = False
                    logger.info(f"Disabled notifications for user {rec.user_id} in org {broadcast.organization_id} after 403")

            else:
                # Any other error code (e.g. 400 Bad Request, 500)
                rec.status = RecipientStatus.FAILED.value
                rec.error_code = str(resp.status_code)
                rec.error_message = resp.text[:500]
                broadcast.failed_count += 1
                logger.warning(f"Failed to send to user {rec.user_id}: {resp.status_code} {resp.text}")

        except Exception as e:
            rec.status = RecipientStatus.FAILED.value
            rec.error_code = "network_error"
            rec.error_message = str(e)[:500]
            broadcast.failed_count += 1
            logger.warning(f"Exception sending to user {rec.user_id}: {e}")

    # Process all recipients sequentially with rate limiter
    if http_client:
        for rec, tg_id in recipients_rows:
            await _send_to_recipient(http_client, rec, tg_id)
            if delay_between_messages > 0:
                await asyncio.sleep(delay_between_messages)
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for rec, tg_id in recipients_rows:
                await _send_to_recipient(client, rec, tg_id)
                if delay_between_messages > 0:
                    await asyncio.sleep(delay_between_messages)

    # Determine final broadcast status
    broadcast.completed_at = utc_now()
    if broadcast.failed_count == 0 and broadcast.blocked_count == 0:
        broadcast.status = BroadcastStatus.COMPLETED.value
    elif broadcast.sent_count > 0:
        broadcast.status = BroadcastStatus.PARTIALLY_FAILED.value
    else:
        broadcast.status = BroadcastStatus.FAILED.value

    await session.commit()
    return broadcast


async def record_broadcast_view(
    session: AsyncSession,
    event_id: str,
    user_id: Optional[int],
    broadcast_token: Optional[str],
) -> bool:
    """
    Attributes an event view to a Telegram broadcast if:
    1. Valid broadcast exists matching attribution_token.
    2. Broadcast is linked to this event_id.
    3. View occurs within BROADCAST_ATTRIBUTION_HOURS (24h) of broadcast.created_at.
    4. User was a recipient of the broadcast.
    Updates recipient.opened_at and recipient.clicked_at.
    Safe and non-blocking: never raises exceptions.
    """
    if not user_id or not broadcast_token or not event_id:
        return False

    try:
        stmt = select(Broadcast).where(Broadcast.attribution_token == broadcast_token)
        res = await session.execute(stmt)
        broadcast = res.scalar_one_or_none()
        if not broadcast:
            logger.info("Broadcast token not found: %s", broadcast_token)
            return False

        # Event match check
        if broadcast.event_id != event_id:
            logger.info(
                "Attribution ignored: broadcast %s event (%s) does not match viewed event (%s)",
                broadcast.id, broadcast.event_id, event_id
            )
            return False

        # Attribution window check (24 hours)
        now = utc_now()
        bcast_created = broadcast.created_at
        if bcast_created.tzinfo is None:
            bcast_created = bcast_created.replace(tzinfo=timezone.utc)

        if now - bcast_created > timedelta(hours=settings.BROADCAST_ATTRIBUTION_HOURS):
            logger.info(
                "Attribution ignored: broadcast %s is outside %d-hour window",
                broadcast.id, settings.BROADCAST_ATTRIBUTION_HOURS
            )
            return False

        # Recipient lookup
        r_stmt = select(BroadcastRecipient).where(
            BroadcastRecipient.broadcast_id == broadcast.id,
            BroadcastRecipient.user_id == user_id,
        )
        r_res = await session.execute(r_stmt)
        recipient = r_res.scalar_one_or_none()
        if not recipient:
            logger.info(
                "Attribution ignored: user %s was not a recipient of broadcast %s",
                user_id, broadcast.id
            )
            return False

        if not recipient.opened_at:
            recipient.opened_at = now
        if not recipient.clicked_at:
            recipient.clicked_at = now

        await session.commit()
        return True
    except Exception as e:
        logger.warning("Error in record_broadcast_view: %s", e)
        return False


async def record_broadcast_conversion(
    session: AsyncSession,
    event_id: str,
    user_id: int,
    conversion_type: str,  # "interest" or "rsvp"
) -> bool:
    """
    Attributes an interest ('Хочу пойти') or RSVP ('Я иду') action to a broadcast if:
    1. User is a recipient of a broadcast for this event within BROADCAST_ATTRIBUTION_HOURS (24h).
    2. User opened the event via that broadcast (opened_at is set).
    3. User did NOT have pre-existing interest/RSVP prior to broadcast.created_at.
    Updates recipient.attributed_interest_at or recipient.attributed_rsvp_at.
    Safe and non-blocking: never raises exceptions.
    """
    if not user_id or not event_id:
        return False

    try:
        now = utc_now()
        cutoff = now - timedelta(hours=settings.BROADCAST_ATTRIBUTION_HOURS)

        # Find recipient where broadcast is for this event, opened_at is set, and broadcast created within 24h
        stmt = (
            select(BroadcastRecipient, Broadcast)
            .join(Broadcast, BroadcastRecipient.broadcast_id == Broadcast.id)
            .where(
                Broadcast.event_id == event_id,
                BroadcastRecipient.user_id == user_id,
                BroadcastRecipient.opened_at.isnot(None),
                Broadcast.created_at >= cutoff,
            )
            .order_by(Broadcast.created_at.desc())
        )
        res = await session.execute(stmt)
        candidates = res.all()
        if not candidates:
            return False

        recipient, broadcast = candidates[0]
        bcast_created = broadcast.created_at
        if bcast_created.tzinfo is None:
            bcast_created = bcast_created.replace(tzinfo=timezone.utc)

        if conversion_type == "interest":
            # Check pre-existing interest before broadcast creation
            prior_stmt = select(EventInterest).where(
                EventInterest.event_id == event_id,
                EventInterest.user_id == user_id,
                EventInterest.created_at < bcast_created,
            )
            prior_res = await session.execute(prior_stmt)
            if prior_res.first():
                logger.info(
                    "Attribution ignored: user %s had pre-existing interest before broadcast %s",
                    user_id, broadcast.id
                )
                return False

            if not recipient.attributed_interest_at:
                recipient.attributed_interest_at = now
                await session.commit()
                return True

        elif conversion_type == "rsvp":
            # Check pre-existing RSVP before broadcast creation
            prior_stmt = select(EventAttendee).where(
                EventAttendee.event_id == event_id,
                EventAttendee.user_id == user_id,
                EventAttendee.created_at < bcast_created,
            )
            prior_res = await session.execute(prior_stmt)
            if prior_res.first():
                logger.info(
                    "Attribution ignored: user %s had pre-existing RSVP before broadcast %s",
                    user_id, broadcast.id
                )
                return False

            if not recipient.attributed_rsvp_at:
                recipient.attributed_rsvp_at = now
                await session.commit()
                return True

        return False
    except Exception as e:
        logger.warning("Error in record_broadcast_conversion: %s", e)
        return False


async def list_organizer_broadcasts(
    session: AsyncSession,
    organizer_user_id: int
) -> List[BroadcastItem]:
    """
    Returns list of broadcasts created by or belonging to organizations owned by the organizer,
    including aggregated attribution analytics.
    """
    subq = (
        select(
            BroadcastRecipient.broadcast_id,
            func.count(case((BroadcastRecipient.opened_at.isnot(None), 1))).label("opened_count"),
            func.count(case((BroadcastRecipient.attributed_interest_at.isnot(None), 1))).label("interest_count"),
            func.count(case((BroadcastRecipient.attributed_rsvp_at.isnot(None), 1))).label("rsvp_count"),
        )
        .group_by(BroadcastRecipient.broadcast_id)
        .subquery()
    )

    stmt = (
        select(
            Broadcast,
            Organization.name.label("org_name"),
            Event.title.label("ev_title"),
            func.coalesce(subq.c.opened_count, 0).label("opened_count"),
            func.coalesce(subq.c.interest_count, 0).label("interest_count"),
            func.coalesce(subq.c.rsvp_count, 0).label("rsvp_count"),
        )
        .join(Organization, Broadcast.organization_id == Organization.id)
        .outerjoin(Event, Broadcast.event_id == Event.id)
        .outerjoin(subq, Broadcast.id == subq.c.broadcast_id)
        .where(Organization.owner_user_id == organizer_user_id)
        .order_by(Broadcast.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    items = []
    for bcast, org_name, ev_title, opened_cnt, interest_cnt, rsvp_cnt in rows:
        delivered = bcast.delivered_count or 0
        items.append(
            BroadcastItem(
                id=bcast.id,
                organization_id=bcast.organization_id,
                organization_name=org_name,
                event_id=bcast.event_id,
                event_title=ev_title,
                target_type=bcast.target_type,
                broadcast_type=bcast.broadcast_type,
                template_key=bcast.template_key,
                custom_text=bcast.custom_text,
                status=bcast.status,
                total_recipients=bcast.total_recipients,
                sent_count=bcast.sent_count,
                delivered_count=bcast.delivered_count,
                failed_count=bcast.failed_count,
                blocked_count=bcast.blocked_count,
                opened_count=opened_cnt or 0,
                interest_count=interest_cnt or 0,
                rsvp_count=rsvp_cnt or 0,
                open_rate=min(round(((opened_cnt or 0) / delivered) * 100, 1), 100.0) if delivered > 0 else 0.0,
                interest_conversion=min(round(((interest_cnt or 0) / delivered) * 100, 1), 100.0) if delivered > 0 else 0.0,
                rsvp_conversion=min(round(((rsvp_cnt or 0) / delivered) * 100, 1), 100.0) if delivered > 0 else 0.0,
                created_at=bcast.created_at,
                started_at=bcast.started_at,
                completed_at=bcast.completed_at,
            )
        )
    return items


async def get_broadcast_detail(
    session: AsyncSession,
    organizer_user_id: int,
    broadcast_id: str
) -> BroadcastDetail:
    """
    Returns detail metrics for a specific broadcast.
    Ensures authorization: only the organization owner can access it.
    """
    stmt = (
        select(Broadcast, Organization, Event)
        .join(Organization, Broadcast.organization_id == Organization.id)
        .outerjoin(Event, Broadcast.event_id == Event.id)
        .where(Broadcast.id == broadcast_id)
    )
    res = await session.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")

    bcast, org, event = row
    if org.owner_user_id != organizer_user_id:
        raise HTTPException(status_code=403, detail="У вас нет прав для просмотра этой рассылки")

    stats_stmt = (
        select(
            func.count(case((BroadcastRecipient.opened_at.isnot(None), 1))).label("opened_count"),
            func.count(case((BroadcastRecipient.attributed_interest_at.isnot(None), 1))).label("interest_count"),
            func.count(case((BroadcastRecipient.attributed_rsvp_at.isnot(None), 1))).label("rsvp_count"),
        )
        .where(BroadcastRecipient.broadcast_id == bcast.id)
    )
    stats_res = await session.execute(stats_stmt)
    stats_row = stats_res.one()
    opened_count = stats_row.opened_count or 0
    interest_count = stats_row.interest_count or 0
    rsvp_count = stats_row.rsvp_count or 0

    delivered = bcast.delivered_count or 0
    open_rate = min(round((opened_count / delivered) * 100, 1), 100.0) if delivered > 0 else 0.0
    interest_conversion = min(round((interest_count / delivered) * 100, 1), 100.0) if delivered > 0 else 0.0
    rsvp_conversion = min(round((rsvp_count / delivered) * 100, 1), 100.0) if delivered > 0 else 0.0

    try:
        message_text, button_text, button_url = format_broadcast_content(
            organization=org,
            template_key=bcast.template_key,
            event=event,
            custom_text=bcast.custom_text,
            broadcast_id=bcast.id,
            attribution_token=bcast.attribution_token,
        )
    except HTTPException:
        # Graceful fallback for historical broadcasts if linked event was removed
        message_text = bcast.custom_text or f"Рассылка от {org.name}"
        button_text = "Открыть профиль 🏛"
        button_url = settings.get_organization_deep_link(org.id)

    return BroadcastDetail(
        id=bcast.id,
        organization_id=bcast.organization_id,
        organization_name=org.name,
        event_id=bcast.event_id,
        event_title=event.title if event else None,
        target_type=bcast.target_type,
        broadcast_type=bcast.broadcast_type,
        template_key=bcast.template_key,
        custom_text=bcast.custom_text,
        status=bcast.status,
        total_recipients=bcast.total_recipients,
        sent_count=bcast.sent_count,
        delivered_count=bcast.delivered_count,
        failed_count=bcast.failed_count,
        blocked_count=bcast.blocked_count,
        opened_count=opened_count,
        interest_count=interest_count,
        rsvp_count=rsvp_count,
        open_rate=open_rate,
        interest_conversion=interest_conversion,
        rsvp_conversion=rsvp_conversion,
        created_at=bcast.created_at,
        started_at=bcast.started_at,
        completed_at=bcast.completed_at,
        message_text=message_text,
        button_text=button_text,
        button_url=button_url,
        attribution_token=bcast.attribution_token,
    )
