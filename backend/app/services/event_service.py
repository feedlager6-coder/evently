from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete, case
from sqlalchemy.orm import selectinload

from fastapi import HTTPException, status

from app.config import settings
from app.models.event import Event, EventStatus, utc_now
from app.models.city import City
from app.models.category import Category
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.user import User
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.view import EventView
from app.models.broadcast import Broadcast, BroadcastRecipient
from app.schemas.event import EventCreate, EventSummary, EventResponse, EventUpdate
from app.schemas.interest import EventInterestResponse


class EventNotFoundError(Exception):
    pass


class EventValidationError(Exception):
    pass


class EventForbiddenError(Exception):
    pass


def resolve_city_timezone(city_tz_str: str):
    """
    Safely resolves timezone with fallback for systems without tzdata installed.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(city_tz_str)
    except Exception:
        offsets = {
            "Europe/Warsaw": 1,
            "Europe/Moscow": 3,
            "UTC": 0,
        }
        hours = offsets.get(city_tz_str, 0)
        return timezone(timedelta(hours=hours))


def get_city_timezone_range(city_tz_str: str, date_filter: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Computes start and end timestamps in UTC based on the local calendar in the city's timezone.
    Guarantees that 'today', 'tomorrow', and 'weekend' reflect the city's actual local time.
    """
    if date_filter == "all" or not date_filter:
        return None, None

    tz = resolve_city_timezone(city_tz_str)
    now_city = datetime.now(tz)
    today_start = now_city.replace(hour=0, minute=0, second=0, microsecond=0)

    if date_filter == "today":
        start_local = today_start
        end_local = today_start + timedelta(days=1)
    elif date_filter == "tomorrow":
        start_local = today_start + timedelta(days=1)
        end_local = today_start + timedelta(days=2)
    elif date_filter == "weekend":
        weekday = now_city.weekday()  # Monday = 0, Sunday = 6
        if weekday == 5:  # Saturday
            start_local = today_start
            end_local = today_start + timedelta(days=2)
        elif weekday == 6:  # Sunday
            start_local = today_start - timedelta(days=1)
            end_local = today_start + timedelta(days=1)
        else:  # Monday to Friday
            days_to_sat = 5 - weekday
            start_local = today_start + timedelta(days=days_to_sat)
            end_local = start_local + timedelta(days=2)
    else:
        return None, None

    # Convert local midnight bounds to UTC
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return start_utc, end_utc


async def list_published_events(
    session: AsyncSession,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
    date_filter: str = "all",
    search_query: Optional[str] = None,
    current_user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[EventSummary], int]:
    """
    Lists published events for public discovery with attendee counts and user RSVP status.
    Uses subquery count aggregation to eliminate N+1 queries.
    """
    # Count subquery for attendees
    attendee_count_subq = (
        select(func.count(EventAttendee.user_id))
        .where(EventAttendee.event_id == Event.id)
        .scalar_subquery()
    )

    # Count subquery for interests
    interest_count_subq = (
        select(func.count(EventInterest.id))
        .where(EventInterest.event_id == Event.id)
        .scalar_subquery()
    )

    # Base query for published events
    query = (
        select(
            Event,
            Category.name.label("category_name"),
            City.name.label("city_name"),
            City.timezone.label("city_timezone"),
            attendee_count_subq.label("attendee_count"),
            interest_count_subq.label("interest_count"),
            Organization.name.label("org_name"),
            Organization.category.label("org_category"),
            Organization.avatar_url.label("org_avatar")
        )
        .join(Category, Event.category_id == Category.id)
        .join(City, Event.city_id == City.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .where(Event.status == EventStatus.PUBLISHED.value)
    )

    now_utc = datetime.now(timezone.utc)

    if city_id:
        query = query.where(Event.city_id == city_id)
        # Apply city timezone-aware date range
        city_res = await session.execute(select(City).where(City.id == city_id))
        city = city_res.scalar_one_or_none()
        if city and date_filter in ("today", "tomorrow", "weekend"):
            start_utc, end_utc = get_city_timezone_range(city.timezone, date_filter)
            if start_utc and end_utc:
                effective_start = max(start_utc, now_utc) if date_filter == "today" else start_utc
                query = query.where(and_(Event.start_at >= effective_start, Event.start_at < end_utc))
        else:
            query = query.where(Event.start_at >= now_utc)
    elif date_filter in ("today", "tomorrow", "weekend"):
        # Default UTC range if city not selected
        start_utc, end_utc = get_city_timezone_range("UTC", date_filter)
        if start_utc and end_utc:
            effective_start = max(start_utc, now_utc) if date_filter == "today" else start_utc
            query = query.where(and_(Event.start_at >= effective_start, Event.start_at < end_utc))
    else:
        query = query.where(Event.start_at >= now_utc)

    if category_id:
        query = query.where(Event.category_id == category_id)

    if search_query and search_query.strip():
        term = f"%{search_query.strip()}%"
        query = query.where(
            or_(
                Event.title.ilike(term),
                Event.description.ilike(term),
                Event.venue_name.ilike(term),
                City.name.ilike(term),
                Category.name.ilike(term)
            )
        )

    # Order chronologically
    query = query.order_by(Event.start_at.asc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_count_res = await session.execute(count_query)
    total = total_count_res.scalar() or 0

    # Paginate
    query = query.limit(limit).offset(offset)
    results = await session.execute(query)
    rows = results.all()

    # Pre-fetch user RSVP and interest event IDs if current_user_id is supplied
    attending_event_ids = set()
    interested_event_ids = set()
    if current_user_id and rows:
        event_ids = [r[0].id for r in rows]
        user_att_q = select(EventAttendee.event_id).where(
            and_(EventAttendee.user_id == current_user_id, EventAttendee.event_id.in_(event_ids))
        )
        att_res = await session.execute(user_att_q)
        attending_event_ids = set(att_res.scalars().all())

        user_int_q = select(EventInterest.event_id).where(
            and_(EventInterest.user_id == current_user_id, EventInterest.event_id.in_(event_ids))
        )
        int_res = await session.execute(user_int_q)
        interested_event_ids = set(int_res.scalars().all())

    summaries: List[EventSummary] = []
    for event, cat_name, c_name, c_tz, att_count, int_count, org_name, org_category, org_avatar in rows:
        summaries.append(
            EventSummary(
                id=event.id,
                title=event.title,
                cover_image_url=event.cover_image_url,
                category_id=event.category_id,
                category_name=cat_name,
                city_id=event.city_id,
                city_name=c_name,
                start_at=event.start_at,
                venue_name=event.venue_name,
                latitude=event.latitude,
                longitude=event.longitude,
                price_amount=event.price_amount,
                price_currency=event.price_currency,
                is_free=(event.price_amount is None or event.price_amount == 0),
                attendee_count=att_count or 0,
                status=event.status,
                is_attending=(event.id in attending_event_ids),
                interest_count=int_count or 0,
                current_user_interested=(event.id in interested_event_ids),
                organization_id=event.organization_id,
                organization_name=org_name,
                organization_category=org_category,
                organization_avatar_url=org_avatar
            )
        )

    return summaries, total


async def get_event_details(
    session: AsyncSession,
    event_id: str,
    current_user_id: Optional[int] = None
) -> EventResponse:
    """
    Fetches complete event details including description, address, organizer, and RSVP status.
    """
    attendee_count_subq = (
        select(func.count(EventAttendee.user_id))
        .where(EventAttendee.event_id == Event.id)
        .scalar_subquery()
    )

    interest_count_subq = (
        select(func.count(EventInterest.id))
        .where(EventInterest.event_id == Event.id)
        .scalar_subquery()
    )

    views_count_subq = (
        select(func.count(EventView.id))
        .where(EventView.event_id == Event.id)
        .scalar_subquery()
    )

    query = (
        select(
            Event,
            Category.name.label("category_name"),
            City.name.label("city_name"),
            attendee_count_subq.label("attendee_count"),
            interest_count_subq.label("interest_count"),
            views_count_subq.label("views_count"),
            User.username.label("org_username"),
            User.first_name.label("org_first_name"),
            Organization.id.label("org_id"),
            Organization.name.label("org_name"),
            Organization.category.label("org_category"),
            Organization.avatar_url.label("org_avatar")
        )
        .join(Category, Event.category_id == Category.id)
        .join(City, Event.city_id == City.id)
        .outerjoin(User, Event.organizer_user_id == User.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .where(Event.id == event_id)
    )

    res = await session.execute(query)
    row = res.first()
    if not row:
        raise EventNotFoundError(f"Event with ID '{event_id}' not found.")

    event, cat_name, c_name, att_count, int_count, raw_views_count, org_username, org_first_name, org_id, org_name, org_category, org_avatar = row
    if event.status == EventStatus.DELETED.value:
        raise EventNotFoundError(f"Event with ID '{event_id}' not found.")

    organizer_display = org_username or org_first_name or None
    is_organizer = bool(current_user_id and current_user_id == event.organizer_user_id)
    # Phase 6: Organizer sees own views_count; public sees 0
    safe_views_count = (raw_views_count or 0) if (current_user_id and current_user_id == event.organizer_user_id) else 0

    # Check RSVP & Interest
    is_attending = False
    is_interested = False
    if current_user_id:
        rsvp_res = await session.execute(
            select(EventAttendee).where(
                and_(EventAttendee.event_id == event_id, EventAttendee.user_id == current_user_id)
            )
        )
        is_attending = rsvp_res.scalar_one_or_none() is not None

        int_res = await session.execute(
            select(EventInterest).where(
                and_(EventInterest.event_id == event_id, EventInterest.user_id == current_user_id)
            )
        )
        is_interested = int_res.scalar_one_or_none() is not None

    # Organization follower stats and subscription status
    org_followers_count = None
    org_is_subscribed = None
    if org_id:
        f_count_res = await session.execute(
            select(func.count(Subscription.id)).where(Subscription.organization_id == org_id)
        )
        org_followers_count = f_count_res.scalar() or 0
        if current_user_id:
            sub_res = await session.execute(
                select(Subscription.id).where(
                    and_(Subscription.organization_id == org_id, Subscription.user_id == current_user_id)
                )
            )
            org_is_subscribed = sub_res.scalar_one_or_none() is not None
        else:
            org_is_subscribed = False

    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        cover_image_url=event.cover_image_url,
        category_id=event.category_id,
        category_name=cat_name,
        city_id=event.city_id,
        city_name=c_name,
        start_at=event.start_at,
        venue_name=event.venue_name,
        address=event.address,
        latitude=event.latitude,
        longitude=event.longitude,
        price_amount=event.price_amount,
        price_currency=event.price_currency,
        is_free=(event.price_amount is None or event.price_amount == 0),
        status=event.status,
        organizer_user_id=event.organizer_user_id,
        organizer_name=organizer_display,
        organization_id=org_id,
        organization_name=org_name,
        organization_category=org_category,
        organization_avatar_url=org_avatar,
        organization_followers_count=org_followers_count,
        organization_is_subscribed=org_is_subscribed,
        is_organizer=is_organizer,
        rejection_reason=event.rejection_reason,
        attendee_count=att_count or 0,
        is_attending=is_attending,
        interest_count=int_count or 0,
        current_user_interested=is_interested,
        views_count=safe_views_count,
        created_at=event.created_at,
        updated_at=event.updated_at
    )


async def add_event_rsvp(
    session: AsyncSession,
    event_id: str,
    user_id: int
) -> Tuple[bool, int, str]:
    """
    Idempotently records event attendance.
    If already attending, returns (True, current_count, 'Already attending') without errors.
    Removes any existing EventInterest since confirmed attendance supersedes interest.
    """
    event_res = await session.execute(select(Event).where(Event.id == event_id))
    event = event_res.scalar_one_or_none()
    if not event or event.status == EventStatus.DELETED.value:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    # Confirmed attendance supersedes interest: remove interest if exists
    del_int_stmt = delete(EventInterest).where(
        and_(EventInterest.event_id == event_id, EventInterest.user_id == user_id)
    )
    await session.execute(del_int_stmt)

    # Check existing attendance
    check_stmt = select(EventAttendee).where(
        and_(EventAttendee.event_id == event_id, EventAttendee.user_id == user_id)
    )
    existing = (await session.execute(check_stmt)).scalar_one_or_none()

    if existing:
        await session.commit()
        # Already attending: idempotent return
        count_res = await session.execute(
            select(func.count(EventAttendee.user_id)).where(EventAttendee.event_id == event_id)
        )
        count = count_res.scalar() or 0
        return True, count, "Already attending"

    # Insert attendance
    attendee = EventAttendee(event_id=event_id, user_id=user_id)
    session.add(attendee)
    await session.commit()

    # Attribution hook for Telegram broadcast conversion
    try:
        from app.services.broadcast_service import record_broadcast_conversion
        await record_broadcast_conversion(session, event_id, user_id, "rsvp")
    except Exception as attr_err:
        logger.warning(f"Broadcast RSVP conversion attribution error: {attr_err}")

    count_res = await session.execute(
        select(func.count(EventAttendee.user_id)).where(EventAttendee.event_id == event_id)
    )
    count = count_res.scalar() or 0
    return True, count, "RSVP confirmed"


async def remove_event_rsvp(
    session: AsyncSession,
    event_id: str,
    user_id: int
) -> Tuple[bool, int, str]:
    """
    Idempotently cancels event attendance.
    If not attending, returns (False, current_count, 'Not attending') safely.
    """
    event_res = await session.execute(select(Event).where(Event.id == event_id))
    event = event_res.scalar_one_or_none()
    if not event or event.status == EventStatus.DELETED.value:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    # Delete attendance if exists
    del_stmt = delete(EventAttendee).where(
        and_(EventAttendee.event_id == event_id, EventAttendee.user_id == user_id)
    )
    await session.execute(del_stmt)
    await session.commit()

    # Hook: auto-disable company discovery profile if user has neither interest nor attendance
    try:
        from app.services.company_service import auto_deactivate_profile_if_not_participating
        await auto_deactivate_profile_if_not_participating(session, event_id, user_id)
    except Exception as e:
        logger.warning(f"Company profile auto-deactivate note: {e}")

    count_res = await session.execute(
        select(func.count(EventAttendee.user_id)).where(EventAttendee.event_id == event_id)
    )
    count = count_res.scalar() or 0
    return False, count, "RSVP removed"


async def add_event_interest(
    session: AsyncSession,
    event_id: str,
    user_id: int
) -> Tuple[bool, int, bool, int, str]:
    """
    Idempotently records user interest ('Хочу пойти').
    If the user was previously attending ('Я иду'), switches from attending to interested.
    Returns: (is_interested, interest_count, is_attending, attendee_count, message)
    """
    event_res = await session.execute(select(Event).where(Event.id == event_id))
    event = event_res.scalar_one_or_none()
    if not event or event.status == EventStatus.DELETED.value:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    # If currently attending, remove attendance (downgrade to interested)
    del_att_stmt = delete(EventAttendee).where(
        and_(EventAttendee.event_id == event_id, EventAttendee.user_id == user_id)
    )
    await session.execute(del_att_stmt)

    # Check if interest already exists
    check_stmt = select(EventInterest).where(
        and_(EventInterest.event_id == event_id, EventInterest.user_id == user_id)
    )
    existing = (await session.execute(check_stmt)).scalar_one_or_none()

    if not existing:
        interest = EventInterest(event_id=event_id, user_id=user_id)
        session.add(interest)

    await session.commit()

    if not existing:
        try:
            from app.services.broadcast_service import record_broadcast_conversion
            await record_broadcast_conversion(session, event_id, user_id, "interest")
        except Exception as attr_err:
            logger.warning(f"Broadcast interest conversion attribution error: {attr_err}")

    int_count_res = await session.execute(
        select(func.count(EventInterest.id)).where(EventInterest.event_id == event_id)
    )
    interest_count = int_count_res.scalar() or 0

    att_count_res = await session.execute(
        select(func.count(EventAttendee.user_id)).where(EventAttendee.event_id == event_id)
    )
    attendee_count = att_count_res.scalar() or 0

    msg = "Already interested" if existing else "Interest confirmed"
    return True, interest_count, False, attendee_count, msg


async def remove_event_interest(
    session: AsyncSession,
    event_id: str,
    user_id: int
) -> Tuple[bool, int, bool, int, str]:
    """
    Idempotently cancels user interest ('Хочу пойти').
    Returns: (is_interested, interest_count, is_attending, attendee_count, message)
    """
    event_res = await session.execute(select(Event).where(Event.id == event_id))
    event = event_res.scalar_one_or_none()
    if not event or event.status == EventStatus.DELETED.value:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    # Delete interest if exists
    del_stmt = delete(EventInterest).where(
        and_(EventInterest.event_id == event_id, EventInterest.user_id == user_id)
    )
    await session.execute(del_stmt)
    await session.commit()

    # Hook: auto-disable company discovery profile if user has neither interest nor attendance
    try:
        from app.services.company_service import auto_deactivate_profile_if_not_participating
        await auto_deactivate_profile_if_not_participating(session, event_id, user_id)
    except Exception as e:
        logger.warning(f"Company profile auto-deactivate note: {e}")

    int_count_res = await session.execute(
        select(func.count(EventInterest.id)).where(EventInterest.event_id == event_id)
    )
    interest_count = int_count_res.scalar() or 0

    # Check attending
    att_res = await session.execute(
        select(EventAttendee).where(
            and_(EventAttendee.event_id == event_id, EventAttendee.user_id == user_id)
        )
    )
    is_attending = att_res.scalar_one_or_none() is not None

    att_count_res = await session.execute(
        select(func.count(EventAttendee.user_id)).where(EventAttendee.event_id == event_id)
    )
    attendee_count = att_count_res.scalar() or 0

    return False, interest_count, is_attending, attendee_count, "Interest removed"


VALID_VIEW_SOURCES = {"discovery", "deep_link", "personal", "organizer", "inline", "broadcast", "unknown"}


async def record_event_view(
    session: AsyncSession,
    event_id: str,
    user_id: Optional[int] = None,
    source: Optional[str] = "unknown",
    broadcast_token: Optional[str] = None
) -> Tuple[bool, int]:
    """
    Records a canonical event view with 2h deduplication for authenticated users and author exclusion.
    Hooks into Telegram broadcast attribution if broadcast_token is provided.
    Returns: (recorded: bool, views_count: int)
    """
    event_res = await session.execute(select(Event).where(Event.id == event_id))
    event = event_res.scalar_one_or_none()
    if not event:
        raise EventNotFoundError(f"Мероприятие '{event_id}' не найдено.")

    if event.status != EventStatus.PUBLISHED.value:
        raise EventValidationError("Нельзя просматривать неопубликованное мероприятие")

    # Attribution hook for Telegram broadcast
    if broadcast_token and user_id:
        try:
            from app.services.broadcast_service import record_broadcast_view
            await record_broadcast_view(session, event_id, user_id, broadcast_token)
        except Exception as attr_err:
            logger.warning(f"Broadcast attribution hook error: {attr_err}")

    # Author cannot bump their own event view counter
    if user_id and event.organizer_user_id == user_id:
        views_cnt_res = await session.execute(
            select(func.count(EventView.id)).where(EventView.event_id == event_id)
        )
        return False, views_cnt_res.scalar() or 0

    clean_source = (source or "unknown").strip().lower()
    if clean_source not in VALID_VIEW_SOURCES:
        clean_source = "unknown"

    # Deduplication for authenticated user: max 1 view per 2 hours
    if user_id is not None:
        window_start = datetime.now(timezone.utc) - timedelta(hours=2)
        recent_view_q = select(EventView.id).where(
            and_(
                EventView.event_id == event_id,
                EventView.user_id == user_id,
                EventView.created_at >= window_start
            )
        ).limit(1)
        recent_view = (await session.execute(recent_view_q)).scalar_one_or_none()
        if recent_view:
            views_cnt_res = await session.execute(
                select(func.count(EventView.id)).where(EventView.event_id == event_id)
            )
            return False, views_cnt_res.scalar() or 0

    new_view = EventView(
        event_id=event_id,
        user_id=user_id,
        source=clean_source
    )
    session.add(new_view)
    await session.commit()

    views_cnt_res = await session.execute(
        select(func.count(EventView.id)).where(EventView.event_id == event_id)
    )
    return True, views_cnt_res.scalar() or 0


async def create_organizer_event(
    session: AsyncSession,
    data: EventCreate,
    organizer_user_id: int
) -> Event:
    """
    Creates an event submitted by an organizer. Always enters 'pending' state.
    """
    # Verify city and category exist
    city_res = await session.execute(select(City).where(City.id == data.city_id))
    if not city_res.scalar_one_or_none():
        raise EventValidationError(f"Invalid city_id '{data.city_id}'")

    cat_res = await session.execute(select(Category).where(Category.id == data.category_id))
    if not cat_res.scalar_one_or_none():
        raise EventValidationError(f"Invalid category_id '{data.category_id}'")

    org_id = None
    org = None
    if data.organization_id:
        org_res = await session.execute(select(Organization).where(Organization.id == data.organization_id))
        org = org_res.scalar_one_or_none()
        if not org or org.status != "active":
            raise EventValidationError("Указанная организация не найдена или отключена")
        if org.owner_user_id != organizer_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не можете создавать мероприятия от имени чужой организации"
            )
        org_id = org.id

    resolved_address = (data.address or "").strip()
    if not resolved_address:
        if org and org.address:
            resolved_address = org.address.strip()
        else:
            resolved_address = data.venue_name.strip()

    resolved_lat = data.latitude
    resolved_lng = data.longitude
    if resolved_lat is None and resolved_lng is None and org:
        resolved_lat = org.latitude
        resolved_lng = org.longitude

    event = Event(
        title=data.title,
        description=data.description,
        cover_image_url=data.cover_image_url,
        category_id=data.category_id,
        city_id=data.city_id,
        start_at=data.start_at,
        venue_name=data.venue_name,
        address=resolved_address,
        latitude=resolved_lat,
        longitude=resolved_lng,
        price_amount=data.price_amount,
        price_currency=data.price_currency or "RUB",
        status=EventStatus.PENDING.value,
        organizer_user_id=organizer_user_id,
        organization_id=org_id
    )

    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def update_organizer_event(
    session: AsyncSession,
    event_id: str,
    data: EventUpdate,
    user_id: int
) -> Tuple[Event, Dict[str, Any]]:
    """
    Updates an event submitted by an organizer.
    Strictly verifies ownership:
    - 404 if event not found or deleted
    - 403 (EventForbiddenError) if user is not organizer or org owner
    Detects operational changes (start_at, venue_name, address).
    If published and significant change occurs, automatically triggers notify_event_updated.
    """
    res = await session.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event or event.status == EventStatus.DELETED.value:
        raise EventNotFoundError(f"Мероприятие '{event_id}' не найдено.")

    is_owner = (event.organizer_user_id == user_id)
    if not is_owner and event.organization_id:
        org_res = await session.execute(select(Organization).where(Organization.id == event.organization_id))
        org = org_res.scalar_one_or_none()
        if org and org.owner_user_id == user_id:
            is_owner = True

    user_res = await session.execute(select(User).where(User.id == user_id))
    current_u = user_res.scalar_one_or_none()
    is_admin = bool(current_u and settings.is_admin(current_u.telegram_id))
    if not is_owner and is_admin:
        is_owner = True

    if not is_owner:
        raise EventForbiddenError("У вас нет прав для изменения этого мероприятия.")

    old_start_at = event.start_at
    old_venue_name = event.venue_name
    old_address = event.address

    changes: Dict[str, Any] = {}
    time_changed = False
    venue_changed = False

    if data.start_at is not None and data.start_at != event.start_at:
        time_changed = True
        changes["time_changed"] = True
        changes["old_start_at"] = old_start_at
        changes["new_start_at"] = data.start_at
        event.start_at = data.start_at

    if data.venue_name is not None and data.venue_name.strip() != event.venue_name:
        venue_changed = True
        changes["venue_changed"] = True
        changes["old_venue"] = old_venue_name
        changes["new_venue"] = data.venue_name.strip()
        event.venue_name = data.venue_name.strip()

    if data.address is not None and data.address.strip() != (event.address or ""):
        if not venue_changed:
            changes["venue_changed"] = True
            changes["old_venue"] = old_address or old_venue_name
            changes["new_venue"] = data.address.strip()
        event.address = data.address.strip()

    if data.title is not None and data.title.strip():
        event.title = data.title.strip()
    if data.description is not None and data.description.strip():
        event.description = data.description.strip()
    if data.cover_image_url is not None:
        event.cover_image_url = data.cover_image_url
    if data.latitude is not None:
        event.latitude = data.latitude
    if data.longitude is not None:
        event.longitude = data.longitude
    if data.price_amount is not None:
        event.price_amount = data.price_amount
    if data.price_currency is not None:
        event.price_currency = data.price_currency

    if data.category_id is not None and data.category_id.strip():
        cat_res = await session.execute(select(Category).where(Category.id == data.category_id.strip()))
        if not cat_res.scalar_one_or_none():
            raise EventValidationError(f"Invalid category_id '{data.category_id}'")
        event.category_id = data.category_id.strip()

    if data.city_id is not None and data.city_id.strip():
        city_res = await session.execute(select(City).where(City.id == data.city_id.strip()))
        if not city_res.scalar_one_or_none():
            raise EventValidationError(f"Invalid city_id '{data.city_id}'")
        event.city_id = data.city_id.strip()

    if data.organization_id is not None:
        org_id_val = data.organization_id.strip()
        if not org_id_val or org_id_val.lower() in ("none", "null"):
            event.organization_id = None
        else:
            org_res = await session.execute(select(Organization).where(Organization.id == org_id_val))
            target_org = org_res.scalar_one_or_none()
            if not target_org or target_org.status != "active":
                raise EventValidationError("Указанная организация не найдена или отключена")
            if target_org.owner_user_id != user_id and not is_admin:
                raise EventForbiddenError("Вы не можете привязать мероприятие к чужой организации")
            event.organization_id = target_org.id

    event.updated_at = utc_now()
    await session.commit()
    await session.refresh(event)

    # If published and operational change occurred, dispatch system transactional notification
    if event.status == EventStatus.PUBLISHED.value and (time_changed or venue_changed):
        try:
            from app.services.notification_service import notify_event_updated
            await notify_event_updated(event, changes, session)
        except Exception as notif_err:
            logger.warning(f"Error dispatching event update notifications for event {event.id}: {notif_err}")

    return event, changes


async def delete_organizer_event(
    session: AsyncSession,
    event_id: str,
    user_id: int
) -> Event:
    """
    Safely marks an organizer's event as deleted (soft delete).
    Strictly verifies ownership:
    - 404 if event not found or already deleted
    - 403 (EventForbiddenError) if user is not the organizer or organization owner
    Preserves historical analytics, views, attendees, interests, and broadcasts.
    Automatically dispatches cancellation notification if the event was published.
    """
    res = await session.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event or event.status == EventStatus.DELETED.value:
        raise EventNotFoundError(f"Мероприятие '{event_id}' не найдено.")

    # Check ownership: organizer_user_id or organization owner or admin
    is_owner = (event.organizer_user_id == user_id)
    if not is_owner and event.organization_id:
        org_res = await session.execute(select(Organization).where(Organization.id == event.organization_id))
        org = org_res.scalar_one_or_none()
        if org and org.owner_user_id == user_id:
            is_owner = True

    if not is_owner:
        user_res = await session.execute(select(User).where(User.id == user_id))
        current_u = user_res.scalar_one_or_none()
        if current_u and settings.is_admin(current_u.telegram_id):
            is_owner = True

    if not is_owner:
        raise EventForbiddenError("У вас нет прав для удаления этого мероприятия.")

    was_published = (event.status == EventStatus.PUBLISHED.value)
    event.status = EventStatus.DELETED.value
    event.updated_at = utc_now()
    await session.commit()

    if was_published:
        try:
            from app.services.notification_service import notify_event_cancelled
            await notify_event_cancelled(event, session)
        except Exception as e:
            logger.warning(f"Failed to dispatch cancellation notification on event deletion {event_id}: {e}")

    return event


async def get_organizer_events(
    session: AsyncSession,
    organizer_user_id: int
) -> List[EventSummary]:
    """
    Lists all events submitted by a specific organizer across all statuses.
    """
    attendee_count_subq = (
        select(func.count(EventAttendee.user_id))
        .where(EventAttendee.event_id == Event.id)
        .scalar_subquery()
    )
    interest_count_subq = (
        select(func.count(EventInterest.user_id))
        .where(EventInterest.event_id == Event.id)
        .scalar_subquery()
    )
    views_count_subq = (
        select(func.count(EventView.id))
        .where(EventView.event_id == Event.id)
        .scalar_subquery()
    )

    query = (
        select(
            Event,
            Category.name.label("category_name"),
            City.name.label("city_name"),
            attendee_count_subq.label("attendee_count"),
            interest_count_subq.label("interest_count"),
            views_count_subq.label("views_count"),
            Organization.name.label("org_name"),
            Organization.category.label("org_category"),
            Organization.avatar_url.label("org_avatar")
        )
        .join(Category, Event.category_id == Category.id)
        .join(City, Event.city_id == City.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .where(
            and_(
                Event.organizer_user_id == organizer_user_id,
                Event.status != EventStatus.DELETED.value
            )
        )
        .order_by(Event.created_at.desc())
    )

    results = await session.execute(query)
    rows = results.all()

    # Aggregate broadcast attribution metrics for organizer's events
    broadcast_stats_map = {}
    event_ids = [event.id for event, *_ in rows]
    if event_ids:
        bcast_subq = (
            select(
                Broadcast.event_id,
                func.count(case((BroadcastRecipient.opened_at.isnot(None), 1))).label("opened_count"),
                func.count(case((BroadcastRecipient.attributed_interest_at.isnot(None), 1))).label("interest_count"),
                func.count(case((BroadcastRecipient.attributed_rsvp_at.isnot(None), 1))).label("rsvp_count"),
            )
            .join(BroadcastRecipient, Broadcast.id == BroadcastRecipient.broadcast_id)
            .where(Broadcast.event_id.in_(event_ids))
            .group_by(Broadcast.event_id)
        )
        bcast_res = await session.execute(bcast_subq)
        for ev_id, o_cnt, i_cnt, r_cnt in bcast_res.all():
            broadcast_stats_map[ev_id] = (o_cnt or 0, i_cnt or 0, r_cnt or 0)

    summaries = []
    for event, cat_name, c_name, att_count, int_count, v_count, org_name, org_category, org_avatar in rows:
        b_opens, b_interest, b_rsvp = broadcast_stats_map.get(event.id, (0, 0, 0))
        summaries.append(
            EventSummary(
                id=event.id,
                title=event.title,
                cover_image_url=event.cover_image_url,
                category_id=event.category_id,
                category_name=cat_name,
                city_id=event.city_id,
                city_name=c_name,
                start_at=event.start_at,
                venue_name=event.venue_name,
                latitude=event.latitude,
                longitude=event.longitude,
                price_amount=event.price_amount,
                price_currency=event.price_currency,
                is_free=(event.price_amount is None or event.price_amount == 0),
                attendee_count=att_count or 0,
                status=event.status,
                is_attending=False,
                interest_count=int_count or 0,
                current_user_interested=False,
                views_count=v_count or 0,
                organization_id=event.organization_id,
                organization_name=org_name,
                organization_category=org_category,
                organization_avatar_url=org_avatar,
                broadcast_opens_count=b_opens,
                broadcast_interest_count=b_interest,
                broadcast_rsvp_count=b_rsvp,
            )
        )
    return summaries


async def get_user_personal_events(
    session: AsyncSession,
    user_id: int,
    event_type: str = "attending",
    limit: int = 50,
    offset: int = 0
) -> List[EventSummary]:
    """
    Returns events for the authenticated user based on type:
    - 'attending': events where user clicked 'Я иду' (EventAttendee)
    - 'interested': events where user clicked 'Хочу пойти' (EventInterest)
    """
    attendee_count_subq = (
        select(func.count(EventAttendee.user_id))
        .where(EventAttendee.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )
    interest_count_subq = (
        select(func.count(EventInterest.user_id))
        .where(EventInterest.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )

    query = (
        select(
            Event,
            Category.name.label("category_name"),
            City.name.label("city_name"),
            attendee_count_subq.label("attendee_count"),
            interest_count_subq.label("interest_count"),
            Organization.name.label("org_name"),
            Organization.category.label("org_category"),
            Organization.avatar_url.label("org_avatar")
        )
        .join(Category, Event.category_id == Category.id)
        .join(City, Event.city_id == City.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
    )

    if event_type == "interested":
        target_event_ids_q = select(EventInterest.event_id).where(EventInterest.user_id == user_id)
        query = query.where(Event.id.in_(target_event_ids_q))
    else:
        target_event_ids_q = select(EventAttendee.event_id).where(EventAttendee.user_id == user_id)
        query = query.where(Event.id.in_(target_event_ids_q))

    # Show published or cancelled events (preserve personal event history)
    query = query.where(Event.status.in_([EventStatus.PUBLISHED.value, EventStatus.CANCELLED.value]))
    # Order by start_at ascending (upcoming events first)
    query = query.order_by(Event.start_at.asc()).limit(limit).offset(offset)

    results = await session.execute(query)
    rows = results.all()

    summaries = []
    for event, cat_name, c_name, att_count, int_count, org_name, org_category, org_avatar in rows:
        summaries.append(
            EventSummary(
                id=event.id,
                title=event.title,
                cover_image_url=event.cover_image_url,
                category_id=event.category_id,
                category_name=cat_name,
                city_id=event.city_id,
                city_name=c_name,
                start_at=event.start_at,
                venue_name=event.venue_name,
                latitude=event.latitude,
                longitude=event.longitude,
                price_amount=event.price_amount,
                price_currency=event.price_currency,
                is_free=(event.price_amount is None or event.price_amount == 0),
                attendee_count=att_count or 0,
                status=event.status,
                is_attending=(event_type == "attending"),
                interest_count=int_count or 0,
                current_user_interested=(event_type == "interested"),
                organization_id=event.organization_id,
                organization_name=org_name,
                organization_category=org_category,
                organization_avatar_url=org_avatar
            )
        )
    return summaries

