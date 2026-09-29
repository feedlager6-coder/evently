from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.orm import selectinload

from fastapi import HTTPException, status

from app.models.event import Event, EventStatus
from app.models.city import City
from app.models.category import Category
from app.models.attendee import EventAttendee
from app.models.user import User
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.schemas.event import EventCreate, EventSummary, EventResponse


class EventNotFoundError(Exception):
    pass


class EventValidationError(Exception):
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

    # Base query for published events
    query = (
        select(
            Event,
            Category.name.label("category_name"),
            City.name.label("city_name"),
            City.timezone.label("city_timezone"),
            attendee_count_subq.label("attendee_count"),
            Organization.name.label("org_name"),
            Organization.category.label("org_category"),
            Organization.avatar_url.label("org_avatar")
        )
        .join(Category, Event.category_id == Category.id)
        .join(City, Event.city_id == City.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .where(Event.status == EventStatus.PUBLISHED.value)
    )

    if city_id:
        query = query.where(Event.city_id == city_id)
        # Apply city timezone-aware date range
        city_res = await session.execute(select(City).where(City.id == city_id))
        city = city_res.scalar_one_or_none()
        if city and date_filter in ("today", "tomorrow", "weekend"):
            start_utc, end_utc = get_city_timezone_range(city.timezone, date_filter)
            if start_utc and end_utc:
                query = query.where(and_(Event.start_at >= start_utc, Event.start_at < end_utc))
    elif date_filter in ("today", "tomorrow", "weekend"):
        # Default UTC range if city not selected
        start_utc, end_utc = get_city_timezone_range("UTC", date_filter)
        if start_utc and end_utc:
            query = query.where(and_(Event.start_at >= start_utc, Event.start_at < end_utc))

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

    # Pre-fetch user RSVP event IDs if current_user_id is supplied
    attending_event_ids = set()
    if current_user_id and rows:
        event_ids = [r[0].id for r in rows]
        user_att_q = select(EventAttendee.event_id).where(
            and_(EventAttendee.user_id == current_user_id, EventAttendee.event_id.in_(event_ids))
        )
        att_res = await session.execute(user_att_q)
        attending_event_ids = set(att_res.scalars().all())

    summaries: List[EventSummary] = []
    for event, cat_name, c_name, c_tz, att_count, org_name, org_category, org_avatar in rows:
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

    query = (
        select(
            Event,
            Category.name.label("category_name"),
            City.name.label("city_name"),
            attendee_count_subq.label("attendee_count"),
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

    event, cat_name, c_name, att_count, org_username, org_first_name, org_id, org_name, org_category, org_avatar = row
    organizer_display = org_username or org_first_name or None

    # Check RSVP
    is_attending = False
    if current_user_id:
        rsvp_res = await session.execute(
            select(EventAttendee).where(
                and_(EventAttendee.event_id == event_id, EventAttendee.user_id == current_user_id)
            )
        )
        is_attending = rsvp_res.scalar_one_or_none() is not None

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
        rejection_reason=event.rejection_reason,
        attendee_count=att_count or 0,
        is_attending=is_attending,
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
    """
    event_res = await session.execute(select(Event).where(Event.id == event_id))
    event = event_res.scalar_one_or_none()
    if not event:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    # Check existing attendance
    check_stmt = select(EventAttendee).where(
        and_(EventAttendee.event_id == event_id, EventAttendee.user_id == user_id)
    )
    existing = (await session.execute(check_stmt)).scalar_one_or_none()

    if existing:
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
    if not event:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    # Delete attendance if exists
    del_stmt = delete(EventAttendee).where(
        and_(EventAttendee.event_id == event_id, EventAttendee.user_id == user_id)
    )
    await session.execute(del_stmt)
    await session.commit()

    count_res = await session.execute(
        select(func.count(EventAttendee.user_id)).where(EventAttendee.event_id == event_id)
    )
    count = count_res.scalar() or 0
    return False, count, "RSVP removed"


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

    query = (
        select(
            Event,
            Category.name.label("category_name"),
            City.name.label("city_name"),
            attendee_count_subq.label("attendee_count"),
            Organization.name.label("org_name"),
            Organization.category.label("org_category"),
            Organization.avatar_url.label("org_avatar")
        )
        .join(Category, Event.category_id == Category.id)
        .join(City, Event.city_id == City.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .where(Event.organizer_user_id == organizer_user_id)
        .order_by(Event.created_at.desc())
    )

    results = await session.execute(query)
    rows = results.all()

    summaries = []
    for event, cat_name, c_name, att_count, org_name, org_category, org_avatar in rows:
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
                organization_id=event.organization_id,
                organization_name=org_name,
                organization_category=org_category,
                organization_avatar_url=org_avatar
            )
        )
    return summaries
