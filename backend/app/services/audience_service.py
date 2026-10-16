import logging
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, case, union

from app.models.organization import Organization, OrganizationStatus
from app.models.subscription import Subscription
from app.models.event import Event, EventStatus
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.view import EventView
from app.models.city import City
from app.schemas.audience import (
    OrganizerAudienceResponse,
    OrganizationAudienceItem,
    EventAudienceItem,
    DailyGrowthPoint,
)

logger = logging.getLogger("evently.audience")


async def get_organizer_audience(
    session: AsyncSession,
    organizer_user_id: int,
    target_org_id: Optional[str] = None
) -> OrganizerAudienceResponse:
    """
    Computes verified audience metrics for the authenticated organizer.
    
    Strict constraints:
    - Authorizes access: organizers can only view their owned organizations and events.
    - Zero vanity/fabricated metrics: no fake attribution or simulated ROI.
    - Zero personal data leaks: telegram_id and private user details are never returned.
    """
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    # 1. Fetch and validate owned organizations
    if target_org_id:
        org_res = await session.execute(
            select(Organization, City.name.label("city_name"))
            .outerjoin(City, Organization.city_id == City.id)
            .where(
                Organization.id == target_org_id,
                Organization.status != OrganizationStatus.DELETED.value
            )
        )
        row = org_res.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Организация не найдена"
            )
        target_org, city_name = row
        if target_org.owner_user_id != organizer_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен: вы не являетесь владельцем этой организации"
            )
        owned_orgs = [(target_org, city_name)]
    else:
        org_res = await session.execute(
            select(Organization, City.name.label("city_name"))
            .outerjoin(City, Organization.city_id == City.id)
            .where(
                Organization.owner_user_id == organizer_user_id,
                Organization.status != OrganizationStatus.DELETED.value
            )
            .order_by(Organization.created_at.desc())
        )
        owned_orgs = org_res.all()

    owned_org_ids = [org.id for org, _ in owned_orgs]

    # 2. Query events belonging to organizer (filtered by target_org_id if specified)
    if target_org_id:
        event_query = select(Event).where(
            Event.organization_id == target_org_id,
            Event.status != EventStatus.DELETED.value
        )
    else:
        if owned_org_ids:
            event_query = select(Event).where(
                or_(
                    Event.organizer_user_id == organizer_user_id,
                    Event.organization_id.in_(owned_org_ids)
                ),
                Event.status != EventStatus.DELETED.value
            )
        else:
            event_query = select(Event).where(
                Event.organizer_user_id == organizer_user_id,
                Event.status != EventStatus.DELETED.value
            )

    event_res = await session.execute(event_query.order_by(Event.start_at.desc()))
    all_events = event_res.scalars().all()
    all_event_ids = [e.id for e in all_events]

    # 3. Compute event-level metrics (views, interest, attendees)
    event_metrics = {}
    if all_event_ids:
        # Views per event
        views_stmt = (
            select(EventView.event_id, func.count(EventView.id))
            .where(EventView.event_id.in_(all_event_ids))
            .group_by(EventView.event_id)
        )
        views_res = await session.execute(views_stmt)
        views_map = dict(views_res.all())

        # Interest per event
        interest_stmt = (
            select(EventInterest.event_id, func.count(EventInterest.id))
            .where(EventInterest.event_id.in_(all_event_ids))
            .group_by(EventInterest.event_id)
        )
        interest_res = await session.execute(interest_stmt)
        interest_map = dict(interest_res.all())

        # Attendees per event
        attendees_stmt = (
            select(EventAttendee.event_id, func.count(EventAttendee.user_id))
            .where(EventAttendee.event_id.in_(all_event_ids))
            .group_by(EventAttendee.event_id)
        )
        attendees_res = await session.execute(attendees_stmt)
        attendees_map = dict(attendees_res.all())

        for ev in all_events:
            event_metrics[ev.id] = {
                "views": views_map.get(ev.id, 0),
                "interest": interest_map.get(ev.id, 0),
                "attendees": attendees_map.get(ev.id, 0),
            }

    # 4. Compute organization-level breakdown
    org_items: List[OrganizationAudienceItem] = []
    total_subs = 0
    total_new_7d = 0
    total_new_30d = 0

    org_events_map = {}
    for ev in all_events:
        if ev.organization_id:
            org_events_map.setdefault(ev.organization_id, []).append(ev)

    for org, city_name in owned_orgs:
        # Subscribers metrics
        sub_count_stmt = select(func.count(Subscription.id)).where(Subscription.organization_id == org.id)
        sub_count = (await session.execute(sub_count_stmt)).scalar() or 0

        sub_7d_stmt = select(func.count(Subscription.id)).where(
            Subscription.organization_id == org.id,
            Subscription.created_at >= d7
        )
        sub_7d = (await session.execute(sub_7d_stmt)).scalar() or 0

        sub_30d_stmt = select(func.count(Subscription.id)).where(
            Subscription.organization_id == org.id,
            Subscription.created_at >= d30
        )
        sub_30d = (await session.execute(sub_30d_stmt)).scalar() or 0

        total_subs += sub_count
        total_new_7d += sub_7d
        total_new_30d += sub_30d

        org_evs = org_events_map.get(org.id, [])
        org_views = sum(event_metrics.get(e.id, {}).get("views", 0) for e in org_evs)
        org_interest = sum(event_metrics.get(e.id, {}).get("interest", 0) for e in org_evs)
        org_attendees = sum(event_metrics.get(e.id, {}).get("attendees", 0) for e in org_evs)

        org_items.append(
            OrganizationAudienceItem(
                id=org.id,
                name=org.name,
                slug=org.slug,
                avatar_url=org.avatar_url,
                category=org.category,
                city_name=city_name,
                subscribers_count=sub_count,
                new_subscribers_7d=sub_7d,
                new_subscribers_30d=sub_30d,
                events_count=len(org_evs),
                total_views=org_views,
                total_interest=org_interest,
                total_attendees=org_attendees,
            )
        )

    # 5. Global activity totals across all events
    total_views = sum(m["views"] for m in event_metrics.values())
    total_interest = sum(m["interest"] for m in event_metrics.values())
    total_attendees = sum(m["attendees"] for m in event_metrics.values())

    # 6. Total unique engaged users and honest daily growth calculation
    user_first_seen: dict[int, datetime] = {}

    if owned_org_ids:
        sub_users_res = await session.execute(
            select(Subscription.user_id, Subscription.created_at)
            .where(Subscription.organization_id.in_(owned_org_ids))
        )
        for uid, cat in sub_users_res.all():
            if cat and (uid not in user_first_seen or cat < user_first_seen[uid]):
                user_first_seen[uid] = cat

    if all_event_ids:
        att_users_res = await session.execute(
            select(EventAttendee.user_id, EventAttendee.created_at)
            .where(EventAttendee.event_id.in_(all_event_ids))
        )
        for uid, cat in att_users_res.all():
            if cat and (uid not in user_first_seen or cat < user_first_seen[uid]):
                user_first_seen[uid] = cat

        int_users_res = await session.execute(
            select(EventInterest.user_id, EventInterest.created_at)
            .where(EventInterest.event_id.in_(all_event_ids))
        )
        for uid, cat in int_users_res.all():
            if cat and (uid not in user_first_seen or cat < user_first_seen[uid]):
                user_first_seen[uid] = cat

    total_unique_engaged = len(user_first_seen)

    # 30-Day Growth Timeline (strictly in Europe/Moscow timezone)
    try:
        from zoneinfo import ZoneInfo
        msk_tz = ZoneInfo("Europe/Moscow")
    except Exception:
        msk_tz = timezone(timedelta(hours=3))

    now_msk = datetime.now(timezone.utc).astimezone(msk_tz)
    today_date = now_msk.date()
    start_date = today_date - timedelta(days=29)

    user_join_dates = {}
    for uid, dt in user_first_seen.items():
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        user_join_dates[uid] = dt.astimezone(msk_tz).date()

    # Pre-window users count towards baseline
    baseline_count = sum(1 for d in user_join_dates.values() if d < start_date)

    month_names = {
        1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
        7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек"
    }

    daily_growth: List[DailyGrowthPoint] = []
    running_cumulative = baseline_count
    d7_date = today_date - timedelta(days=6)
    new_subscribers_7d_count = 0
    new_subscribers_30d_count = 0
    new_subscribers_today = 0

    for i in range(30):
        current_day = start_date + timedelta(days=i)
        day_new = sum(1 for d in user_join_dates.values() if d == current_day)
        running_cumulative += day_new

        date_str = current_day.strftime("%Y-%m-%d")
        label_str = f"{current_day.day} {month_names.get(current_day.month, '')}"

        daily_growth.append(DailyGrowthPoint(
            date=date_str,
            label=label_str,
            new_count=day_new,
            cumulative_count=running_cumulative
        ))

        new_subscribers_30d_count += day_new
        if current_day >= d7_date:
            new_subscribers_7d_count += day_new
        if current_day == today_date:
            new_subscribers_today = day_new

    # 7. Recent events list (up to 10 for audience feedback)
    recent_events_items: List[EventAudienceItem] = []
    org_dict = {org.id: org.name for org, _ in owned_orgs}
    for ev in all_events[:10]:
        m = event_metrics.get(ev.id, {"views": 0, "interest": 0, "attendees": 0})
        recent_events_items.append(
            EventAudienceItem(
                id=ev.id,
                title=ev.title,
                start_at=ev.start_at,
                venue_name=ev.venue_name,
                status=ev.status,
                organization_id=ev.organization_id,
                organization_name=org_dict.get(ev.organization_id) if ev.organization_id else None,
                views_count=m["views"],
                interest_count=m["interest"],
                attendee_count=m["attendees"],
            )
        )

    return OrganizerAudienceResponse(
        total_subscribers=total_subs,
        new_subscribers_today=new_subscribers_today,
        new_subscribers_7d=new_subscribers_7d_count,
        new_subscribers_30d=new_subscribers_30d_count,
        total_views=total_views,
        total_interest=total_interest,
        total_attendees=total_attendees,
        total_unique_engaged=total_unique_engaged,
        daily_growth=daily_growth,
        organizations=org_items,
        recent_events=recent_events_items,
    )
