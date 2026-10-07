import logging
import html
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.event import Event, EventStatus
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.user import User
from app.models.city import City
from app.database import AsyncSessionLocal

logger = logging.getLogger("evently.notifications")


from pathlib import Path
import json


def resolve_local_cover_path(url: Optional[str]) -> Optional[Path]:
    """
    If event cover image points to a local upload (/uploads/...), checks if the file
    exists on disk in the persistent uploads directory.
    Returns the absolute Path if present, otherwise None.
    """
    if not url or not url.strip():
        return None
    clean = url.strip()
    if clean.startswith("/uploads/"):
        rel_path = clean[len("/uploads/"):]
    elif clean.startswith("uploads/"):
        rel_path = clean[len("uploads/"):]
    else:
        return None
    try:
        from app.services.storage_service import storage_service
        local_dir = storage_service.get_local_storage_dir()
        candidate = local_dir / rel_path
        if candidate.exists() and candidate.is_file():
            return candidate
    except Exception:
        pass
    return None


def resolve_event_cover_url(url: Optional[str]) -> Optional[str]:
    """
    Ensures event cover URL sent to Telegram is a valid absolute HTTP/HTTPS URL, or None.
    Never returns internal filesystem paths (e.g. /app/uploads/...) or relative URLs.
    If no valid public host or URL is provided, returns None so callers fall back to text.
    """
    if not url or not url.strip():
        return None
    clean = url.strip()
    if clean.startswith("http://") or clean.startswith("https://"):
        return clean
    public_host = settings.effective_public_host
    if public_host:
        if not clean.startswith("/"):
            clean = f"/{clean}"
        return f"{public_host}{clean}"
    return None


async def send_telegram_event_message(
    client: httpx.AsyncClient,
    bot_token: str,
    chat_id: int,
    text: str,
    reply_markup: Dict[str, Any],
    image_url: Optional[str] = None,
    raw_image_url: Optional[str] = None
) -> bool:
    """
    Delivers a unified Telegram photo+caption message if image_url or local file is available,
    with an immediate and graceful fallback to standard sendMessage if sendPhoto fails
    or if image_url is not provided.
    """
    # 1. First priority: if local upload exists, upload directly via multipart to avoid external crawler issues
    local_path = resolve_local_cover_path(raw_image_url or image_url)
    if local_path:
        try:
            photo_bytes = local_path.read_bytes()
            files = {"photo": (local_path.name, photo_bytes, "image/jpeg")}
            data = {
                "chat_id": str(chat_id),
                "caption": text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(reply_markup)
            }
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                data=data,
                files=files,
                timeout=8.0
            )
            if resp.status_code == 200:
                resp_json = resp.json() if resp.text else {}
                if resp_json.get("ok") is not False:
                    return True
            if resp.status_code == 400:
                logger.warning(
                    f"Multipart sendPhoto rejected with status 400 for chat_id {chat_id}, falling back to sendMessage: {resp.text}"
                )
            else:
                logger.warning(
                    f"Multipart sendPhoto failed with status {resp.status_code} for chat_id {chat_id}, skipping text fallback to prevent duplicate delivery."
                )
                return False
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            logger.warning(f"Multipart sendPhoto network timeout/error for chat_id {chat_id}: {e}. Skipping text fallback.")
            return False
        except Exception as e:
            logger.warning(f"Multipart sendPhoto exception for chat_id {chat_id}: {e}")
            return False

    elif image_url:
        photo_payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }
        try:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                json=photo_payload,
                timeout=6.0
            )
            if resp.status_code == 200:
                resp_json = resp.json() if resp.text else {}
                if resp_json.get("ok") is not False:
                    return True
            if resp.status_code == 400:
                logger.warning(
                    f"sendPhoto rejected with status 400 for chat_id {chat_id}, falling back to sendMessage: {resp.text}"
                )
            else:
                logger.warning(
                    f"sendPhoto failed with status {resp.status_code} for chat_id {chat_id}, skipping text fallback to prevent duplicate delivery."
                )
                return False
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            logger.warning(f"sendPhoto network timeout/error for chat_id {chat_id}: {e}. Skipping text fallback to prevent duplicate delivery.")
            return False
        except Exception as e:
            logger.warning(f"sendPhoto exception for chat_id {chat_id}: {e}")
            return False

    # Fallback to standard sendMessage
    msg_payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }
    try:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=msg_payload,
            timeout=5.0
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"sendMessage exception for chat_id {chat_id}: {e}")
        return False


async def notify_organization_subscribers(
    event_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
    session: Optional[AsyncSession] = None
) -> int:
    """
    Sends Telegram notifications to all active subscribers of an organization
    when a new event is published.
    
    Strict constraints:
    - Never triggers for pending or rejected events.
    - Only sends if event has a valid organization_id and is PUBLISHED.
    - Uses event cover photo if available, with safe fallback.
    - Does not expose subscriber identities.
    - Resilient to individual Telegram delivery errors.
    """
    if session is not None:
        return await _dispatch_notifications(session, event_id, http_client)

    # If get_db is overridden in test environment, use overridden test session
    try:
        from app.main import app
        from app.database import get_db
        if get_db in app.dependency_overrides:
            override = app.dependency_overrides[get_db]
            async for test_sess in override():
                return await _dispatch_notifications(test_sess, event_id, http_client)
    except Exception as e:
        logger.debug(f"Dependency override resolution note: {e}")

    async with AsyncSessionLocal() as sess:
        return await _dispatch_notifications(sess, event_id, http_client)


def build_event_notification_reply_markup(event_id: str, attribution_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Builds official Telegram Mini App inline keyboard for direct private chat messages.
    Uses 'web_app' button targeting public host with ?startapp= parameter for immediate
    in-app loading without external browser redirect hoops.
    """
    param = f"event_{event_id}"
    if attribution_token:
        param = f"event_{event_id}_b_{attribution_token}"
    web_app_url = f"{settings.effective_public_host}/?startapp={param}"
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Открыть событие 🧭",
                    "web_app": {"url": web_app_url}
                }
            ]
        ]
    }


async def _dispatch_notifications(
    session: AsyncSession,
    event_id: str,
    http_client: Optional[httpx.AsyncClient] = None
) -> int:
    # Load event with city and organization
    stmt = (
        select(Event, Organization, City.name.label("city_name"))
        .join(Organization, Event.organization_id == Organization.id)
        .outerjoin(City, Event.city_id == City.id)
        .where(Event.id == event_id)
    )
    res = await session.execute(stmt)
    row = res.first()

    if not row:
        logger.info(f"Notification skipped: Event '{event_id}' has no associated organization.")
        return 0

    event, org, city_name = row

    # STRICT CHECK: Event must be published
    if event.status != EventStatus.PUBLISHED.value:
        logger.warning(
            f"Notification blocked: Event '{event_id}' is not in published status (status='{event.status}')."
        )
        return 0

    # Query all active subscribers with their Telegram IDs
    sub_stmt = (
        select(User.telegram_id)
        .join(Subscription, Subscription.user_id == User.id)
        .where(
            Subscription.organization_id == org.id,
            Subscription.notifications_enabled == True,
            User.telegram_id.isnot(None)
        )
    )
    sub_res = await session.execute(sub_stmt)
    telegram_ids = [tid for tid in sub_res.scalars().all() if tid]

    if not telegram_ids:
        logger.info(f"No active subscribers found for organization '{org.name}' ({org.id}).")
        return 0

    # Prepare message content
    date_str = event.start_at.strftime("%d.%m.%Y в %H:%M")
    safe_org_name = html.escape(org.name)
    safe_title = html.escape(event.title)
    safe_venue = html.escape(event.venue_name)
    safe_city = html.escape(city_name or event.city_id or "")

    message_text = (
        f"🔔 <b>Новое событие от {safe_org_name}</b>\n\n"
        f"🧭 <b>{safe_title}</b>\n"
        f"📅 {date_str}\n"
        f"📍 {safe_venue}"
    )
    if safe_city:
        message_text += f" ({safe_city})"

    reply_markup = build_event_notification_reply_markup(event.id)

    image_url = resolve_event_cover_url(event.cover_image_url)

    logger.info(f"Dispatching notifications for event '{event.id}' to {len(telegram_ids)} subscribers...")

    sent_count = 0
    bot_token = settings.clean_bot_token

    # Check if live bot or mocked client
    if not settings.is_live_bot and http_client is None:
        logger.info(f"[Test/Dev Mode] Simulated notification dispatch to {len(telegram_ids)} subscribers. Image: {image_url}")
        return len(telegram_ids)

    async def _send(client: httpx.AsyncClient, tg_id: int):
        nonlocal sent_count
        ok = await send_telegram_event_message(
            client=client,
            bot_token=bot_token,
            chat_id=tg_id,
            text=message_text,
            reply_markup=reply_markup,
            image_url=image_url,
            raw_image_url=event.cover_image_url
        )
        if ok:
            sent_count += 1

    if http_client:
        for tg_id in telegram_ids:
            await _send(http_client, tg_id)
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for tg_id in telegram_ids:
                await _send(client, tg_id)

    logger.info(f"Completed notification dispatch for event '{event.id}': {sent_count}/{len(telegram_ids)} sent.")
    return sent_count


async def notify_event_updated(
    event: Event,
    changes: Dict[str, Any],
    session: AsyncSession,
    http_client: Optional[httpx.AsyncClient] = None
) -> int:
    """
    Sends transactional Telegram notifications when an event's time or venue is updated.
    Recipients: ONLY confirmed attendees (EventAttendee / 'Я иду').
    Zero general subscribers, zero viewers, zero city-wide blasts.
    Does NOT count against marketing quota, does NOT attach marketing attribution tokens.
    """
    # 1. Gather distinct recipient Telegram IDs (ONLY explicit participants: EventAttendee + EventInterest)
    recipient_ids: Set[int] = set()

    # Confirmed attendees ('Я иду')
    att_stmt = (
        select(User.telegram_id)
        .join(EventAttendee, EventAttendee.user_id == User.id)
        .where(EventAttendee.event_id == event.id, User.telegram_id.isnot(None))
    )
    for tid in (await session.execute(att_stmt)).scalars().all():
        if tid:
            recipient_ids.add(tid)

    # Interested users ('Хочу пойти')
    int_stmt = (
        select(User.telegram_id)
        .join(EventInterest, EventInterest.user_id == User.id)
        .where(EventInterest.event_id == event.id, User.telegram_id.isnot(None))
    )
    for tid in (await session.execute(int_stmt)).scalars().all():
        if tid:
            recipient_ids.add(tid)

    if not recipient_ids:
        logger.info(f"No attendees or interested users for event update notification (event {event.id})")
        return 0

    # 2. Build structured message
    safe_title = html.escape(event.title)
    safe_venue = html.escape(event.venue_name)

    change_lines: List[str] = []
    if changes.get("time_changed"):
        old_time = changes.get("old_start_at")
        new_time = changes.get("new_start_at")
        old_str = old_time.strftime("%d.%m.%Y в %H:%M") if isinstance(old_time, datetime) else str(old_time)
        new_str = new_time.strftime("%d.%m.%Y в %H:%M") if isinstance(new_time, datetime) else str(new_time)
        change_lines.append(f"Время начала изменилось:\nБыло: {old_str}\nСтало: {new_str}")

    if changes.get("venue_changed"):
        old_venue = html.escape(changes.get("old_venue") or "")
        new_venue = html.escape(changes.get("new_venue") or event.venue_name)
        change_lines.append(f"Место проведения изменилось:\nБыло: {old_venue}\nСтало: {new_venue}")

    details = "\n\n".join(change_lines)
    message_text = (
        f"🔔 <b>Изменение события</b>\n\n"
        f"🧭 <b>{safe_title}</b>\n\n"
        f"{details}\n\n"
        f"📍 {safe_venue}"
    )

    reply_markup = build_event_notification_reply_markup(event.id)

    image_url = resolve_event_cover_url(event.cover_image_url)
    bot_token = settings.clean_bot_token

    if not settings.is_live_bot and http_client is None:
        logger.info(f"[Test/Dev Mode] Simulated event update notification to {len(recipient_ids)} users.")
        return len(recipient_ids)

    sent_count = 0
    async def _send(client: httpx.AsyncClient, tg_id: int):
        nonlocal sent_count
        ok = await send_telegram_event_message(
            client=client,
            bot_token=bot_token,
            chat_id=tg_id,
            text=message_text,
            reply_markup=reply_markup,
            image_url=image_url,
            raw_image_url=event.cover_image_url
        )
        if ok:
            sent_count += 1

    if http_client:
        for tg_id in recipient_ids:
            await _send(http_client, tg_id)
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for tg_id in recipient_ids:
                await _send(client, tg_id)

    return sent_count


async def notify_event_cancelled(
    event: Event,
    session: AsyncSession,
    http_client: Optional[httpx.AsyncClient] = None
) -> int:
    """
    Sends transactional Telegram notifications when an event is cancelled.
    Recipients: ONLY confirmed attendees (EventAttendee) and interested users (EventInterest / 'Хочу пойти'), deduplicated.
    Zero general subscribers, zero viewers, zero city-wide blasts.
    Does NOT count against marketing quota, does NOT attach marketing attribution tokens.
    """
    recipient_ids: Set[int] = set()

    # Attendees
    att_stmt = (
        select(User.telegram_id)
        .join(EventAttendee, EventAttendee.user_id == User.id)
        .where(EventAttendee.event_id == event.id, User.telegram_id.isnot(None))
    )
    for tid in (await session.execute(att_stmt)).scalars().all():
        if tid:
            recipient_ids.add(tid)

    # Interested (deduplicated into set)
    int_stmt = (
        select(User.telegram_id)
        .join(EventInterest, EventInterest.user_id == User.id)
        .where(EventInterest.event_id == event.id, User.telegram_id.isnot(None))
    )
    for tid in (await session.execute(int_stmt)).scalars().all():
        if tid:
            recipient_ids.add(tid)

    if not recipient_ids:
        logger.info(f"No recipients for event cancellation notification (event {event.id})")
        return 0

    safe_title = html.escape(event.title)
    safe_venue = html.escape(event.venue_name)
    message_text = (
        f"❌ <b>Событие отменено</b>\n\n"
        f"🧭 <b>{safe_title}</b>\n\n"
        f"К сожалению, организатор отменил событие.\n\n"
        f"📍 {safe_venue}"
    )

    deep_link = settings.get_event_deep_link(event.id)
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "Открыть событие 🧭",
                    "url": deep_link,
                    "style": "primary"
                }
            ]
        ]
    }

    image_url = resolve_event_cover_url(event.cover_image_url)
    bot_token = settings.clean_bot_token

    if not settings.is_live_bot and http_client is None:
        logger.info(f"[Test/Dev Mode] Simulated event cancel notification to {len(recipient_ids)} users.")
        return len(recipient_ids)

    sent_count = 0
    async def _send(client: httpx.AsyncClient, tg_id: int):
        nonlocal sent_count
        ok = await send_telegram_event_message(
            client=client,
            bot_token=bot_token,
            chat_id=tg_id,
            text=message_text,
            reply_markup=reply_markup,
            image_url=image_url,
            raw_image_url=event.cover_image_url
        )
        if ok:
            sent_count += 1

    if http_client:
        for tg_id in recipient_ids:
            await _send(http_client, tg_id)
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for tg_id in recipient_ids:
                await _send(client, tg_id)

    return sent_count


async def notify_company_request(
    event_id: str,
    event_title: str,
    sender_first_name: str,
    receiver_telegram_id: Optional[int],
    http_client: Optional[httpx.AsyncClient] = None
) -> bool:
    """
    Sends a discreet Telegram notification to receiver when someone wants to attend an event together.
    Strict privacy: does NOT leak sender's username before mutual match.
    Uses existing event deep-link. Never throws (failure does not break company request).
    """
    if not receiver_telegram_id:
        return False

    deep_link = settings.get_event_deep_link(event_id)
    safe_sender = html.escape(sender_first_name or "Пользователь Ivently")
    safe_title = html.escape(event_title or "Событие")
    message_text = (
        f"👋 <b>{safe_sender}</b> хочет пойти с вами на событие!\n\n"
        f"🧭 <b>{safe_title}</b>"
    )
    reply_markup = build_event_notification_reply_markup(event_id)

    if not settings.is_live_bot and http_client is None:
        logger.info(f"[Test/Dev Mode] Simulated company request notification to telegram_id {receiver_telegram_id}. Deep link: {deep_link}")
        return True

    payload = {
        "chat_id": receiver_telegram_id,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }
    bot_token = settings.clean_bot_token

    try:
        if http_client:
            resp = await http_client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload,
                timeout=5.0
            )
            return resp.status_code == 200
        else:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json=payload,
                    timeout=5.0
                )
                return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to deliver company request notification to {receiver_telegram_id}: {e}")
        return False


async def send_telegram_notification(
    chat_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    http_client: Optional[httpx.AsyncClient] = None
) -> bool:
    """
    Sends a direct transactional message to a single Telegram chat_id.
    Safely handles test/dev mode without live bot tokens.
    """
    if not settings.is_live_bot and http_client is None:
        logger.info(f"[Test/Dev Mode] Simulated telegram notification to chat_id {chat_id}: {text}")
        return True

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    bot_token = settings.clean_bot_token

    try:
        if http_client:
            resp = await http_client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload,
                timeout=5.0
            )
            return resp.status_code == 200
        else:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json=payload,
                    timeout=5.0
                )
                return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to deliver telegram notification to {chat_id}: {e}")
        return False


async def notify_event_reminder(
    event: Event,
    user: User,
    local_time_str: str,
    session: AsyncSession,
    http_client: Optional[httpx.AsyncClient] = None
) -> bool:
    """
    Sends a personal same-day reminder to an attendee or interested user.
    Uses native web_app button to open the event in Mini App.
    """
    if not user.telegram_id:
        return False

    safe_title = html.escape(event.title)
    safe_venue = html.escape(event.venue_name)

    message_text = (
        f"🔔 <b>Напоминание о событии</b>\n\n"
        f"🧭 <b>{safe_title}</b>\n\n"
        f"📅 Сегодня в {local_time_str}\n"
        f"📍 {safe_venue}"
    )

    reply_markup = build_event_notification_reply_markup(event.id)
    image_url = resolve_event_cover_url(event.cover_image_url)
    bot_token = settings.clean_bot_token

    if not settings.is_live_bot and http_client is None:
        logger.info(f"[Test/Dev Mode] Simulated event reminder to user {user.id} (tg {user.telegram_id}) for event {event.id}.")
        return True

    async def _send(client: httpx.AsyncClient) -> bool:
        return await send_telegram_event_message(
            client=client,
            bot_token=bot_token,
            chat_id=user.telegram_id,
            text=message_text,
            reply_markup=reply_markup,
            image_url=image_url,
            raw_image_url=event.cover_image_url
        )

    if http_client:
        return await _send(http_client)
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await _send(client)

