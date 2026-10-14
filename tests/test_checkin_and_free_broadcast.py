import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.organization import Organization
from app.models.event import Event, EventStatus
from app.models.user import User
from app.models.ticket_checkin import TicketCheckIn
from app.services.telegram_bot import format_event_date_str


@pytest.mark.asyncio
async def test_persistent_ticket_checkin_and_duplicate(client, test_session):
    """Verifies persistent DB check-in, authorization with organizer_user_id, and duplicate prevention."""
    organizer_user_id = 998877
    organizer_auth = {"Authorization": f"tma {make_test_init_data(user_id=organizer_user_id, username='checkin_org')}"}

    # Ensure organizer user exists
    user = (await test_session.execute(select(User).where(User.id == organizer_user_id))).scalar_one_or_none()
    if not user:
        user = User(id=organizer_user_id, telegram_id=organizer_user_id, username="checkin_org")
        test_session.add(user)
        await test_session.commit()

    # Create event owned by this organizer
    event = Event(
        title="CheckIn Concert 2026",
        description="Testing persistent ticket checkin",
        category_id="concerts",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Concert Hall",
        address="Central Ave 1",
        organizer_user_id=organizer_user_id,
        status=EventStatus.PUBLISHED.value,
        price_amount=0,
    )
    test_session.add(event)
    await test_session.commit()

    # 1. First check-in: Should succeed and be stored in ticket_checkins table
    ticket_payload = f'{{"ticket_id": "IVN-TEST-1234", "event_id": "{event.id}", "guest_name": "Алиса Ивентовна"}}'
    resp = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=organizer_auth,
        json={"ticket_code": ticket_payload}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["ticket_code"] == "IVN-TEST-1234"
    assert data["guest_name"] == "Алиса Ивентовна"
    assert data["is_payment_required_at_door"] is False

    # Verify directly in DB
    db_checkin = (await test_session.execute(
        select(TicketCheckIn).where(
            TicketCheckIn.event_id == event.id,
            TicketCheckIn.ticket_code == "IVN-TEST-1234"
        )
    )).scalar_one_or_none()
    assert db_checkin is not None
    assert db_checkin.guest_name == "Алиса Ивентовна"

    # 2. Duplicate check-in: Should return already_checked_in with previous time
    resp_dup = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=organizer_auth,
        json={"ticket_code": "IVN-TEST-1234"}
    )
    assert resp_dup.status_code == 200
    dup_data = resp_dup.json()
    assert dup_data["status"] == "already_checked_in"
    assert "уже был использован" in dup_data["message"]


@pytest.mark.asyncio
async def test_paid_event_door_payment_checkin(client, test_session):
    """Verifies that paid events without external ticket URL trigger is_payment_required_at_door."""
    organizer_user_id = 998878
    organizer_auth = {"Authorization": f"tma {make_test_init_data(user_id=organizer_user_id, username='door_pay_org')}"}

    user = (await test_session.execute(select(User).where(User.id == organizer_user_id))).scalar_one_or_none()
    if not user:
        user = User(id=organizer_user_id, telegram_id=organizer_user_id, username="door_pay_org")
        test_session.add(user)
        await test_session.commit()

    event = Event(
        title="Paid Workshop at Door",
        description="Testing door payment flag",
        category_id="business",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        venue_name="Coworking Space",
        address="Tech Street 5",
        organizer_user_id=organizer_user_id,
        status=EventStatus.PUBLISHED.value,
        price_amount=1500,
        source_url=None,  # No external ticket URL
    )
    test_session.add(event)
    await test_session.commit()

    resp = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=organizer_auth,
        json={"ticket_code": "IVN-PAID-001"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["is_payment_required_at_door"] is True
    assert data["price_amount"] == 1500.0
    assert "ОПЛАТА НА ВХОДЕ: 1500 ₽" in data["message"]


def test_telegram_bot_msk_timezone():
    """Verifies event date formatting in Moscow timezone (MSK / UTC+3)."""
    class MockEvent:
        start_at = datetime(2026, 10, 20, 16, 30, tzinfo=timezone.utc)

    # 16:30 UTC -> 19:30 MSK
    result = format_event_date_str(MockEvent())
    assert "20.10.2026 в 19:30" == result

    # Test ISO string format
    class MockIsoEvent:
        start_at = "2026-10-25T15:00:00Z"

    result_iso = format_event_date_str(MockIsoEvent())
    assert "25.10.2026 в 18:00" == result_iso
