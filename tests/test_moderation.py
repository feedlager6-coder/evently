from datetime import datetime, timedelta, timezone
import pytest
from app.models.event import Event, EventStatus
from app.schemas.event import EventCreate
from app.services.event_service import create_organizer_event, list_published_events
from app.services.moderation_service import publish_event, reject_event, cancel_event, get_admin_events
from tests.conftest import make_test_init_data


@pytest.mark.asyncio
async def test_admin_moderation_lifecycle(test_session):
    now = datetime.now(timezone.utc)
    create_data = EventCreate(
        title="Modern Jazz & Wine Tasting",
        description="Evening of live jazz and curated biodynamic wines.",
        category_id="concerts",
        city_id="makhachkala",
        start_at=now + timedelta(days=3),
        venue_name="Wine Loft",
        address="ул. Горького, 15",
        latitude=42.9831,
        longitude=47.5046,
        price_amount=800.0,
        price_currency="RUB"
    )

    # 1. Organizer submits event -> pending
    event = await create_organizer_event(test_session, create_data, organizer_user_id=1)
    assert event.status == EventStatus.PENDING.value

    # Appears in admin pending queue
    pending_queue = await get_admin_events(test_session, status_filter="pending")
    assert any(e.id == event.id for e in pending_queue)

    # 2. Admin publishes event
    pub_event = await publish_event(test_session, event.id)
    assert pub_event.status == EventStatus.PUBLISHED.value

    # Now appears in public discovery
    public_events, _ = await list_published_events(test_session, city_id="makhachkala")
    assert any(e.id == event.id for e in public_events)

    # 3. Admin cancels event
    cancelled_event = await cancel_event(test_session, event.id)
    assert cancelled_event.status == EventStatus.CANCELLED.value

    # No longer appears in public discovery
    public_after_cancel, _ = await list_published_events(test_session, city_id="makhachkala")
    assert not any(e.id == event.id for e in public_after_cancel)


@pytest.mark.asyncio
async def test_admin_reject_with_reason(test_session):
    now = datetime.now(timezone.utc)
    create_data = EventCreate(
        title="Suspicious Unclear Gathering",
        description="Join us for something secretive.",
        category_id="other",
        city_id="makhachkala",
        start_at=now + timedelta(days=1),
        venue_name="Unknown",
        address="Unknown",
        price_amount=None,
        price_currency="RUB"
    )

    event = await create_organizer_event(test_session, create_data, organizer_user_id=1)
    rejected_event = await reject_event(test_session, event.id, reason="Недостаточно информации о месте проведения.")
    assert rejected_event.status == EventStatus.REJECTED.value
    assert rejected_event.rejection_reason == "Недостаточно информации о месте проведения."


@pytest.mark.asyncio
async def test_non_admin_forbidden_on_admin_api(client):
    # Non-admin user (telegram_id 777888999 not in ADMIN_USER_IDS)
    non_admin_init = make_test_init_data(user_id=777888999, username="regular_joe")
    headers = {"Authorization": f"tma {non_admin_init}"}

    resp = await client.get("/api/v1/admin/events", headers=headers)
    assert resp.status_code == 403
    assert "administrator privileges required" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_access_allowed_for_configured_admin(client):
    # Admin user (telegram_id 123456789 in ADMIN_USER_IDS)
    admin_init = make_test_init_data(user_id=123456789, username="boss_admin")
    headers = {"Authorization": f"tma {admin_init}"}

    resp = await client.get("/api/v1/admin/events?status=pending", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_complete_event_moderation_and_discovery_journey(client):
    """
    End-to-End Regression Test:
    1. User creates an event (status: pending).
    2. User sees it in 'My Events' (/organizer/events) with status 'pending'.
    3. Admin opens moderation queue (/admin/events?status=pending) and sees the event.
    4. Admin clicks 'Publish' -> status becomes published.
    5. Event is now visible in public discovery feed (/events?city_id=...).
    """
    # 1. Organizer submits event
    user_init = make_test_init_data(user_id=555666777, username="sprint_organizer")
    user_headers = {"Authorization": f"tma {user_init}"}

    now = datetime.now(timezone.utc)
    new_event_data = {
        "title": "Kazan Tech & Startup Summit",
        "description": "Annual tech summit for developers and startup founders.",
        "cover_image_url": "https://images.unsplash.com/photo-1540575467063-178a50c2df87",
        "category_id": "education",
        "city_id": "kazan",
        "start_at": (now + timedelta(days=4)).isoformat(),
        "venue_name": "ИТ-парк Казань",
        "address": "ул. Петербургская, 52",
        "latitude": 55.7879,
        "longitude": 49.1233,
        "price_amount": 1000.0,
        "price_currency": "RUB"
    }

    create_res = await client.post("/api/v1/events", json=new_event_data, headers=user_headers)
    assert create_res.status_code == 201
    created = create_res.json()
    event_id = created["id"]
    assert created["status"] == "pending"

    # 2. Organizer sees it in "My Events"
    my_events_res = await client.get("/api/v1/organizer/events", headers=user_headers)
    assert my_events_res.status_code == 200
    user_events = my_events_res.json()
    matched = next((e for e in user_events if e["id"] == event_id), None)
    assert matched is not None
    assert matched["status"] == "pending"

    # Public discovery in Kazan does NOT show it yet
    feed_before = await client.get("/api/v1/events?city_id=kazan")
    assert not any(e["id"] == event_id for e in feed_before.json()["events"])

    # 3. Admin opens moderation queue
    admin_init = make_test_init_data(user_id=123456789, username="boss_admin")
    admin_headers = {"Authorization": f"tma {admin_init}"}

    admin_queue_res = await client.get("/api/v1/admin/events?status=pending", headers=admin_headers)
    assert admin_queue_res.status_code == 200
    queue = admin_queue_res.json()
    assert any(e["id"] == event_id for e in queue)

    # 4. Admin publishes the event
    pub_res = await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=admin_headers)
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "published"

    # 5. Event is now visible in the public discovery feed
    feed_after = await client.get("/api/v1/events?city_id=kazan")
    assert feed_after.status_code == 200
    assert any(e["id"] == event_id for e in feed_after.json()["events"])
