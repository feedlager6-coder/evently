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
        city_id="warsaw",
        start_at=now + timedelta(days=3),
        venue_name="Wine Loft",
        address="ul. Mokotowska 15",
        price_amount=80.0,
        price_currency="PLN"
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
    public_events, _ = await list_published_events(test_session, city_id="warsaw")
    assert any(e.id == event.id for e in public_events)

    # 3. Admin cancels event
    cancelled_event = await cancel_event(test_session, event.id)
    assert cancelled_event.status == EventStatus.CANCELLED.value

    # No longer appears in public discovery
    public_after_cancel, _ = await list_published_events(test_session, city_id="warsaw")
    assert not any(e.id == event.id for e in public_after_cancel)


@pytest.mark.asyncio
async def test_admin_reject_with_reason(test_session):
    now = datetime.now(timezone.utc)
    create_data = EventCreate(
        title="Suspicious Unclear Gathering",
        description="Join us for something secretive.",
        category_id="other",
        city_id="warsaw",
        start_at=now + timedelta(days=1),
        venue_name="Unknown",
        address="Unknown",
        price_amount=None,
        price_currency="PLN"
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
