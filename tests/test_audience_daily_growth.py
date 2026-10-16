import pytest
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.models.organization import Organization, OrganizationStatus
from app.models.subscription import Subscription
from app.models.event import Event, EventStatus
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.services.audience_service import get_organizer_audience


@pytest.mark.asyncio
async def test_audience_daily_growth_honest_timeline(test_session):
    """
    Verifies that:
    1. get_organizer_audience returns daily_growth with exactly 30 days.
    2. Subscribers from 3 days ago are NOT counted in 'new_subscribers_today' (which must be 0).
    3. Old subscribers (before 30 days) are counted in baseline_count.
    4. cumulative_count on today equals total_unique_engaged.
    """
    now = datetime.now(timezone.utc)

    # 1. Create organizer and users
    organizer = User(
        telegram_id=987654321,
        username="org_user",
        first_name="Organizer"
    )
    user_old = User(
        telegram_id=111111,
        username="old_subscriber",
        first_name="Old"
    )
    user_past = User(
        telegram_id=222222,
        username="past_subscriber",
        first_name="Past"
    )
    user_recent = User(
        telegram_id=333333,
        username="recent_subscriber",
        first_name="Recent"
    )
    test_session.add_all([organizer, user_old, user_past, user_recent])
    await test_session.commit()

    org = Organization(
        id="org_growth_test",
        name="Growth Club",
        slug="growth-club",
        owner_user_id=organizer.id,
        category="music",
        status=OrganizationStatus.ACTIVE.value
    )
    test_session.add(org)
    await test_session.commit()

    # User Old subscribed 40 days ago (outside 30-day window)
    sub_old = Subscription(
        user_id=user_old.id,
        organization_id=org.id,
        created_at=now - timedelta(days=40)
    )
    # User Past subscribed 5 days ago (inside 30-day window, NOT today)
    sub_past = Subscription(
        user_id=user_past.id,
        organization_id=org.id,
        created_at=now - timedelta(days=5)
    )
    # User Recent RSVP'd to an event 3 days ago (NOT today)
    event = Event(
        id="ev_growth_1",
        title="Concert",
        description="Live concert",
        category_id="music",
        city_id="makhachkala",
        venue_name="Concert Hall",
        address="Central St",
        organizer_user_id=organizer.id,
        organization_id=org.id,
        status=EventStatus.PUBLISHED.value,
        start_at=now + timedelta(days=2)
    )
    test_session.add(event)
    await test_session.commit()

    att_recent = EventAttendee(
        event_id=event.id,
        user_id=user_recent.id,
        created_at=now - timedelta(days=3)
    )

    test_session.add_all([sub_old, sub_past, att_recent])
    await test_session.commit()

    # Query audience
    audience = await get_organizer_audience(test_session, organizer.id, org.id)

    assert audience.total_unique_engaged == 3
    assert len(audience.daily_growth) == 30
    assert audience.new_subscribers_today == 0
    assert audience.new_subscribers_7d == 2  # past (5d ago) + recent (3d ago)
    assert audience.new_subscribers_30d == 2

    # Baseline check: first day of timeline should have cumulative_count = 1 (from user_old 40d ago)
    assert audience.daily_growth[0].cumulative_count == 1
    # Last day (today) cumulative_count should equal total_unique_engaged (3)
    assert audience.daily_growth[-1].cumulative_count == 3
    assert audience.daily_growth[-1].new_count == 0
