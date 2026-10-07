import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Set
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.event import Event, EventStatus
from app.models.city import City
from app.models.user import User
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.reminder import EventReminder
from app.services.event_service import resolve_city_timezone
from app.services.notification_service import notify_event_reminder

logger = logging.getLogger("evently.reminders")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def process_due_reminders(
    session: AsyncSession,
    http_client: Optional[httpx.AsyncClient] = None,
    force_all_daytime: bool = False
) -> Dict[str, Any]:
    """
    Idempotent engine for dispatching same-day event reminders to confirmed attendees
    ('Я иду') and interested users ('Хочу пойти').
    
    Guarantees:
    1. Zero spam: At most ONE reminder per user per event per reminder_type ('same_day').
    2. Excludes past events (start_at <= utc_now()).
    3. Excludes cancelled events (status == 'cancelled').
    4. Excludes deleted events (status == 'deleted').
    5. Timezone correctness: respects local date in the event's city timezone.
    6. Respects daytime window: only dispatches if local hour is >= 09:00 (no night alerts).
    7. Fully free utility: 0 impact on Pro quota or marketing limits.
    """
    now = utc_now()

    # 1. Fetch all published upcoming events with city timezone info
    # Window: events starting within the next 24 hours
    horizon = now + timedelta(hours=24)
    stmt = (
        select(Event, City)
        .join(City, Event.city_id == City.id)
        .where(
            Event.status == EventStatus.PUBLISHED.value,
            Event.start_at > now,
            Event.start_at <= horizon
        )
    )
    res = await session.execute(stmt)
    rows = res.all()

    events_checked = len(rows)
    events_eligible = 0
    reminders_sent = 0
    reminders_skipped = 0

    for event, city in rows:
        city_tz = resolve_city_timezone(city.timezone)
        local_now = now.astimezone(city_tz)
        local_start = event.start_at.astimezone(city_tz)

        # Check: Is it the local calendar day of the event?
        if local_now.date() != local_start.date():
            continue

        # Check: Do not disturb during night hours (< 09:00 local time) unless force flag is set
        if local_now.hour < 9 and not force_all_daytime:
            continue

        events_eligible += 1

        # 2. Collect distinct users with active interest or RSVP
        eligible_users: Dict[int, User] = {}

        # Attendees ('Я иду')
        att_stmt = (
            select(User)
            .join(EventAttendee, EventAttendee.user_id == User.id)
            .where(
                EventAttendee.event_id == event.id,
                User.telegram_id.isnot(None)
            )
        )
        for u in (await session.execute(att_stmt)).scalars().all():
            eligible_users[u.id] = u

        # Interested ('Хочу пойти')
        int_stmt = (
            select(User)
            .join(EventInterest, EventInterest.user_id == User.id)
            .where(
                EventInterest.event_id == event.id,
                User.telegram_id.isnot(None)
            )
        )
        for u in (await session.execute(int_stmt)).scalars().all():
            eligible_users[u.id] = u

        if not eligible_users:
            continue

        # 3. Check existing reminders to guarantee strict idempotency
        user_ids = list(eligible_users.keys())
        existing_stmt = select(EventReminder.user_id).where(
            EventReminder.event_id == event.id,
            EventReminder.user_id.in_(user_ids),
            EventReminder.reminder_type == "same_day"
        )
        already_reminded_ids: Set[int] = set((await session.execute(existing_stmt)).scalars().all())

        local_time_str = local_start.strftime("%H:%M")

        for uid, user in eligible_users.items():
            if uid in already_reminded_ids:
                reminders_skipped += 1
                continue

            try:
                # Dispatch notification
                delivered = await notify_event_reminder(
                    event=event,
                    user=user,
                    local_time_str=local_time_str,
                    session=session,
                    http_client=http_client
                )

                if delivered:
                    # Record reminder row
                    reminder_rec = EventReminder(
                        event_id=event.id,
                        user_id=uid,
                        reminder_type="same_day",
                        reminded_at=now
                    )
                    session.add(reminder_rec)
                    await session.commit()
                    reminders_sent += 1
                    already_reminded_ids.add(uid)
            except Exception as send_err:
                await session.rollback()
                logger.error(
                    f"Failed sending reminder for event {event.id} to user {uid}: {send_err}"
                )

    report = {
        "timestamp": now.isoformat(),
        "events_checked": events_checked,
        "events_eligible": events_eligible,
        "reminders_sent": reminders_sent,
        "reminders_skipped": reminders_skipped,
    }
    logger.info(f"Reminder loop completed: {report}")
    return report
