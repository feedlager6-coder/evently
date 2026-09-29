from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.event import Event, EventStatus
from app.models.city import City
from app.models.category import Category
from app.models.attendee import EventAttendee
from app.schemas.event import EventSummary, EventResponse
from app.services.event_service import EventNotFoundError, EventValidationError


async def get_admin_events(
    session: AsyncSession,
    status_filter: Optional[str] = "pending"
) -> List[EventSummary]:
    """
    Lists events for administrative review.
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
            attendee_count_subq.label("attendee_count")
        )
        .join(Category, Event.category_id == Category.id)
        .join(City, Event.city_id == City.id)
    )

    if status_filter:
        query = query.where(Event.status == status_filter)

    query = query.order_by(Event.created_at.desc())

    results = await session.execute(query)
    rows = results.all()

    summaries = []
    for event, cat_name, c_name, att_count in rows:
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
                is_attending=False
            )
        )
    return summaries


async def publish_event(session: AsyncSession, event_id: str) -> Event:
    """
    Approves and publishes an event, making it visible to normal users in discovery.
    """
    res = await session.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    if event.status == EventStatus.PUBLISHED.value:
        return event  # Idempotent

    event.status = EventStatus.PUBLISHED.value
    event.rejection_reason = None
    await session.commit()
    await session.refresh(event)
    return event


async def reject_event(session: AsyncSession, event_id: str, reason: Optional[str] = None) -> Event:
    """
    Rejects a pending event with an optional explanation.
    """
    res = await session.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    event.status = EventStatus.REJECTED.value
    event.rejection_reason = reason
    await session.commit()
    await session.refresh(event)
    return event


async def cancel_event(session: AsyncSession, event_id: str) -> Event:
    """
    Cancels a published event, removing it from public discovery.
    """
    res = await session.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise EventNotFoundError(f"Event '{event_id}' not found.")

    event.status = EventStatus.CANCELLED.value
    await session.commit()
    await session.refresh(event)
    return event
