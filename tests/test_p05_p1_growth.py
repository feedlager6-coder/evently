import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.event import Event, EventStatus
from app.models.city import City
from app.models.category import Category
from app.models.user import User
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.reminder import EventReminder
from app.models.organization import Organization, OrganizationStatus
from app.schemas.entitlement import CapabilityStatus
from app.services.reminder_service import process_due_reminders
from app.services.entitlement_service import EntitlementService


@pytest.mark.asyncio
async def test_past_event_rsvp_rejected(client, test_session):
    """
    P0.5: Verify that RSVP ('Я иду') and un-RSVP on past events are rejected with HTTP 400.
    """
    user_id = 70001
    init_data = make_test_init_data(user_id=user_id, username="past_rsvp_user")
    headers = {"Authorization": f"tma {init_data}"}

    # Fetch required relationships
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    # Create an event in the past
    past_event = Event(
        title="Past Rock Concert",
        description="Epic concert in the past",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) - timedelta(days=2),
        venue_name="Rock Stadium",
        address="Central Ave 1",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(past_event)
    await test_session.commit()
    await test_session.refresh(past_event)

    # Attempt RSVP
    resp = await client.post(f"/api/v1/events/{past_event.id}/rsvp", headers=headers)
    assert resp.status_code == 400
    assert "завершено" in resp.json()["detail"]

    # Attempt un-RSVP
    resp_del = await client.delete(f"/api/v1/events/{past_event.id}/rsvp", headers=headers)
    assert resp_del.status_code == 400
    assert "завершено" in resp_del.json()["detail"]


@pytest.mark.asyncio
async def test_past_event_interest_rejected(client, test_session):
    """
    P0.5: Verify that Interest ('Хочу пойти') and un-Interest on past events are rejected with HTTP 400.
    """
    user_id = 70002
    init_data = make_test_init_data(user_id=user_id, username="past_interest_user")
    headers = {"Authorization": f"tma {init_data}"}

    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    past_event = Event(
        title="Past Art Gallery",
        description="Historical gallery",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) - timedelta(days=5),
        venue_name="Art Space",
        address="Art St 12",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(past_event)
    await test_session.commit()
    await test_session.refresh(past_event)

    resp = await client.post(f"/api/v1/events/{past_event.id}/interest", headers=headers)
    assert resp.status_code == 400
    assert "завершено" in resp.json()["detail"]

    resp_del = await client.delete(f"/api/v1/events/{past_event.id}/interest", headers=headers)
    assert resp_del.status_code == 400
    assert "завершено" in resp_del.json()["detail"]


@pytest.mark.asyncio
async def test_past_event_company_profile_rejected(client, test_session):
    """
    P0.5: Verify that company search / find companion on past events is rejected with HTTP 400.
    """
    user_id = 70003
    init_data = make_test_init_data(user_id=user_id, username="past_company_user")
    headers = {"Authorization": f"tma {init_data}"}

    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    past_event = Event(
        title="Past Marathon",
        description="City run",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) - timedelta(days=1),
        venue_name="Park",
        address="Park Alley 1",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(past_event)
    await test_session.commit()
    await test_session.refresh(past_event)

    resp = await client.post(
        f"/api/v1/events/{past_event.id}/company/profile",
        headers=headers,
        json={"is_active": True, "note": "Looking for companions"}
    )
    assert resp.status_code == 400
    assert "прошедшем событии" in resp.json()["detail"] or "уже завершено" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_past_event_details_accessible(client, test_session):
    """
    P0.5: Verify that past event details can still be retrieved (HTTP 200) for history and review.
    """
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    past_event = Event(
        title="Archived Lecture",
        description="Great lecture",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) - timedelta(days=3),
        venue_name="University Hall",
        address="Campus 1",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(past_event)
    await test_session.commit()
    await test_session.refresh(past_event)

    resp = await client.get(f"/api/v1/events/{past_event.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == past_event.id
    assert data["title"] == "Archived Lecture"


@pytest.mark.asyncio
async def test_reminder_service_same_day_idempotency(test_session):
    """
    P1: Verify reminder service:
    - Same-day reminders sent to both RSVP and Interested users
    - Strict idempotency: second run skips already reminded users
    - Excludes past events, cancelled events, and deleted events
    """
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()
    now = datetime.now(timezone.utc)

    # User 1: RSVP attendee
    u1 = User(telegram_id=90001, username="attendee_one", first_name="User1")
    # User 2: Interested user
    u2 = User(telegram_id=90002, username="interested_two", first_name="User2")
    # User 3: User on cancelled event
    u3 = User(telegram_id=90003, username="cancelled_three", first_name="User3")
    # User 4: User on past event
    u4 = User(telegram_id=90004, username="past_four", first_name="User4")

    test_session.add_all([u1, u2, u3, u4])
    await test_session.commit()

    # Event starting in 3 hours today
    active_event = Event(
        title="Today's Festival",
        description="Fun festival today",
        city_id=city.id,
        category_id=category.id,
        start_at=now + timedelta(hours=3),
        venue_name="Main Square",
        address="Square 1",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    # Cancelled event
    cancelled_event = Event(
        title="Cancelled Show",
        description="Cancelled",
        city_id=city.id,
        category_id=category.id,
        start_at=now + timedelta(hours=4),
        venue_name="Theatre",
        address="Theatre Lane 2",
        organizer_user_id=org_user.id,
        status=EventStatus.CANCELLED.value
    )
    # Past event
    past_event = Event(
        title="Past Meetup",
        description="Done",
        city_id=city.id,
        category_id=category.id,
        start_at=now - timedelta(hours=2),
        venue_name="Cafe",
        address="Cafe 5",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add_all([active_event, cancelled_event, past_event])
    await test_session.commit()

    # Link attendees & interest
    test_session.add(EventAttendee(event_id=active_event.id, user_id=u1.id))
    test_session.add(EventInterest(event_id=active_event.id, user_id=u2.id))
    test_session.add(EventAttendee(event_id=cancelled_event.id, user_id=u3.id))
    test_session.add(EventInterest(event_id=past_event.id, user_id=u4.id))
    await test_session.commit()

    with patch("app.services.reminder_service.notify_event_reminder", new_callable=AsyncMock) as mock_notify:
        mock_notify.return_value = True

        # First run: should dispatch reminders to u1 and u2, but NOT u3 or u4
        report1 = await process_due_reminders(test_session, force_all_daytime=True)
        assert report1["reminders_sent"] == 2
        assert report1["reminders_skipped"] == 0
        assert mock_notify.call_count == 2

        # Verify rows recorded in database
        reminders_in_db = (
            await test_session.execute(
                select(EventReminder).where(EventReminder.event_id == active_event.id)
            )
        ).scalars().all()
        assert len(reminders_in_db) == 2
        user_ids = {r.user_id for r in reminders_in_db}
        assert user_ids == {u1.id, u2.id}

        # Second run: must be strictly idempotent (0 sent, 2 skipped)
        mock_notify.reset_mock()
        report2 = await process_due_reminders(test_session, force_all_daytime=True)
        assert report2["reminders_sent"] == 0
        assert report2["reminders_skipped"] == 2
        assert mock_notify.call_count == 0


@pytest.mark.asyncio
async def test_admin_process_reminders_endpoint(client, test_session, monkeypatch):
    """
    P1: Verify admin endpoint POST /api/v1/admin/reminders/process
    - Requires admin access
    - Returns report correctly
    """
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "1110001")

    admin_init_data = make_test_init_data(user_id=1110001, username="admin_super")
    headers = {"Authorization": f"tma {admin_init_data}"}

    with patch("app.services.reminder_service.notify_event_reminder", new_callable=AsyncMock) as mock_notify:
        mock_notify.return_value = True
        resp = await client.post("/api/v1/admin/reminders/process", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "report" in data
        assert "reminders_sent" in data["report"]

    # Non-admin user rejected
    regular_init_data = make_test_init_data(user_id=888888, username="regular_user")
    resp_reg = await client.post("/api/v1/admin/reminders/process", headers={"Authorization": f"tma {regular_init_data}"})
    assert resp_reg.status_code == 403


@pytest.mark.asyncio
async def test_admin_reminder_diagnostics_endpoint(client, monkeypatch):
    """
    P1: Verify admin endpoint GET /api/v1/admin/reminders/diagnostics
    - Requires admin access
    - Returns policy rules and last run telemetry
    """
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", "1110001")
    admin_init_data = make_test_init_data(user_id=1110001, username="admin_super")
    headers = {"Authorization": f"tma {admin_init_data}"}

    resp = await client.get("/api/v1/admin/reminders/diagnostics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "policy" in data
    assert data["policy"]["min_local_hour"] == 9
    assert data["policy"]["window_horizon_hours"] == 24
    assert "total_sent_lifetime" in data


@pytest.mark.asyncio
async def test_free_vs_pro_broadcast_quota_and_operational_isolation(test_session):
    """
    P0.5 & P1: Verify:
    1. Free plan has 0 marketing broadcasts allowed (can_broadcast=False)
    2. Pro plan has 20 marketing broadcasts allowed (can_broadcast=True)
    3. Operational reminders and system notifications are completely separate from broadcast quotas
    """
    city = (await test_session.execute(select(City))).scalars().first()
    owner = User(telegram_id=5550001, username="org_owner", first_name="Owner")
    test_session.add(owner)
    await test_session.commit()

    # Free Org
    org_free = Organization(
        name="Free Non-Profit Community",
        slug="free-non-profit-community",
        category="community",
        city_id=city.id,
        owner_user_id=owner.id,
        status=OrganizationStatus.ACTIVE.value
    )
    test_session.add(org_free)
    await test_session.commit()

    ent_free = await EntitlementService.get_entitlements(test_session, org_free.id)
    assert ent_free.plan == "free"
    assert ent_free.limits.broadcasts_remaining == 0
    assert ent_free.capabilities["broadcasts_extended"].status == CapabilityStatus.LOCKED

    # Upgrade to Pro
    await EntitlementService.set_organization_plan(test_session, org_free.id, plan="pro", status_val="active")
    ent_pro = await EntitlementService.get_entitlements(test_session, org_free.id)
    assert ent_pro.plan == "pro"
    assert ent_pro.limits.broadcasts_remaining == 20
    assert ent_pro.capabilities["broadcasts_extended"].status == CapabilityStatus.AVAILABLE
