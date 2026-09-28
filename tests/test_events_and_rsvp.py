from datetime import datetime, timedelta, timezone
import pytest
from app.models.event import Event, EventStatus
from app.schemas.event import EventCreate
from app.services.event_service import (
    list_published_events,
    get_event_details,
    create_organizer_event,
    add_event_rsvp,
    remove_event_rsvp
)


@pytest.mark.asyncio
async def test_created_event_defaults_to_pending(test_session):
    now = datetime.now(timezone.utc)
    create_data = EventCreate(
        title="Exclusive Startup Pitch Night",
        description="Founders pitching to seed investors.",
        cover_image_url="https://images.unsplash.com/photo-1515187029135-18ee286d815b",
        category_id="business",
        city_id="warsaw",
        start_at=now + timedelta(days=2),
        venue_name="Venture Hub",
        address="ul. Chmielna 10, Warszawa",
        price_amount=50.0,
        price_currency="PLN"
    )

    event = await create_organizer_event(test_session, create_data, organizer_user_id=1)
    assert event.id is not None
    assert event.status == EventStatus.PENDING.value


@pytest.mark.asyncio
async def test_published_visible_others_invisible(test_session):
    now = datetime.now(timezone.utc)

    # 1. Create a pending event
    pending_data = EventCreate(
        title="Secret Gathering (Pending)",
        description="Not yet approved by admin.",
        category_id="parties",
        city_id="warsaw",
        start_at=now + timedelta(days=1),
        venue_name="Secret Basement",
        address="ul. Ukryta 1",
        price_amount=None,
        price_currency="PLN"
    )
    pending_event = await create_organizer_event(test_session, pending_data, organizer_user_id=1)

    # Query public discovery feed
    events, total = await list_published_events(test_session, city_id="warsaw")
    event_ids = [e.id for e in events]

    assert pending_event.id not in event_ids
    # All returned events must be published
    for e in events:
        assert e.status == EventStatus.PUBLISHED.value


@pytest.mark.asyncio
async def test_rsvp_idempotency(test_session):
    # Use existing published Warsaw event
    events, _ = await list_published_events(test_session, city_id="warsaw")
    target_event = events[0]
    initial_count = target_event.attendee_count
    user_id = 999

    # 1. First RSVP: creates attendance
    is_attending_1, count_1, msg_1 = await add_event_rsvp(test_session, target_event.id, user_id=user_id)
    assert is_attending_1 is True
    assert count_1 == initial_count + 1
    assert "confirmed" in msg_1.lower()

    # 2. Second RSVP: idempotent, no duplicate record or double counting
    is_attending_2, count_2, msg_2 = await add_event_rsvp(test_session, target_event.id, user_id=user_id)
    assert is_attending_2 is True
    assert count_2 == count_1  # Count does not increment again
    assert "already attending" in msg_2.lower()

    # 3. First DELETE: cancels attendance
    is_attending_3, count_3, msg_3 = await remove_event_rsvp(test_session, target_event.id, user_id=user_id)
    assert is_attending_3 is False
    assert count_3 == initial_count
    assert "removed" in msg_3.lower()

    # 4. Second DELETE: idempotent, safe
    is_attending_4, count_4, msg_4 = await remove_event_rsvp(test_session, target_event.id, user_id=user_id)
    assert is_attending_4 is False
    assert count_4 == initial_count
