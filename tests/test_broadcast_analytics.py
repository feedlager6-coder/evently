import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.organization import Organization
from app.models.event import Event, EventStatus
from app.models.interest import EventInterest
from app.models.attendee import EventAttendee
from app.models.user import User
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
)


def make_event_payload(org_id: str, title: str = "Acoustic Night", days: int = 5):
    return {
        "title": title,
        "description": "Live musical performance with high quality acoustic sound.",
        "category_id": "concerts",
        "city_id": "makhachkala",
        "start_at": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
        "organization_id": org_id,
        "venue_name": "Main Hall",
    }


@pytest.fixture(autouse=True)
def setup_broadcast_tests(monkeypatch):
    """Bypasses entitlement quota and capability check for D4 broadcast analytics internal tests."""
    from app.services.entitlement_service import EntitlementService
    async def mock_check(session, org_id, capability):
        return True, "Allowed in test", None
    async def mock_enforce(session, org_id, broadcast_type="marketing"):
        return True
    async def mock_require(session, org_id, capability):
        return True
    monkeypatch.setattr(EntitlementService, "check_capability", mock_check)
    monkeypatch.setattr(EntitlementService, "enforce_broadcast_capacity", mock_enforce)
    monkeypatch.setattr(EntitlementService, "require_entitlement", mock_require)


@pytest.mark.asyncio
async def test_broadcast_token_generation_and_deep_link(client, test_session):
    """Verifies attribution token generation and Telegram 64-char limit compliance."""
    owner_id = 9001
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_attr')}"}

    # 1. Create Org
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Attribution Venue", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    # 2. Create Event
    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Acoustic Night", 5),
        headers=auth_owner,
    )
    assert res_ev.status_code == 201
    event_id = res_ev.json()["id"]

    # Approve event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # 3. User subscribes
    sub_user_id = 9101
    auth_sub = {"Authorization": f"tma {make_test_init_data(user_id=sub_user_id, username='sub_user1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_sub)

    # 4. Create Broadcast
    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
            "custom_text": "Не пропустите!",
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    data = res_bcast.json()

    # Verify token is 16-hex char string
    token = data.get("attribution_token")
    assert token is not None
    assert len(token) == 16
    assert all(c in "0123456789abcdef" for c in token)

    # Verify button_url contains _b_{token}
    button_url = data["button_url"]
    assert f"startapp=event_{event_id}_b_{token}" in button_url

    # Verify Telegram 64-char parameter limit
    startapp_param = button_url.split("startapp=")[1]
    assert len(startapp_param) <= 64
    assert len(startapp_param) == 61  # event_ (6) + uuid (36) + _b_ (3) + hex(16) = 61 chars


@pytest.mark.asyncio
async def test_get_event_deep_link_formatting():
    """Direct verification of deep link formatting and length guarantee."""
    dummy_uuid = "12345678-1234-1234-1234-123456789abc"
    dummy_token = "0123456789abcdef"

    link_with_token = settings.get_event_deep_link(dummy_uuid, attribution_token=dummy_token)
    assert f"startapp=event_{dummy_uuid}_b_{dummy_token}" in link_with_token
    param = link_with_token.split("startapp=")[1]
    assert len(param) == 61
    assert len(param) <= 64

    link_plain = settings.get_event_deep_link(dummy_uuid)
    assert f"startapp=event_{dummy_uuid}" in link_plain
    assert "_b_" not in link_plain


@pytest.mark.asyncio
async def test_broadcast_view_attribution_lifecycle(client, test_session):
    """
    Tests end-to-end attribution lifecycle:
    Broadcast sent -> Recipient opens -> Attributed Interest -> Attributed RSVP.
    """
    owner_id = 9002
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_life')}"}

    # Org & Event
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Jazz Basement", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Jazz Jam", 2),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Recipient user
    recipient_uid = 9201
    auth_recipient = {"Authorization": f"tma {make_test_init_data(user_id=recipient_uid, username='jazz_fan')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_recipient)

    # Deliver broadcast
    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    bcast_data = res_bcast.json()
    broadcast_id = bcast_data["id"]
    token = bcast_data["attribution_token"]

    # Before view: opened_count = 0
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{broadcast_id}", headers=auth_owner)
    assert detail_res.json()["opened_count"] == 0
    assert detail_res.json()["open_rate"] == 0.0

    # 1. User views event via broadcast link
    view_res = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "broadcast", "broadcast_token": token},
        headers=auth_recipient,
    )
    assert view_res.status_code == 200
    assert view_res.json()["recorded"] is True

    # Check recipient DB record
    u_db = (await test_session.execute(select(User).where(User.telegram_id == recipient_uid))).scalar_one()
    rec_db = (await test_session.execute(
        select(BroadcastRecipient).where(
            BroadcastRecipient.broadcast_id == broadcast_id,
            BroadcastRecipient.user_id == u_db.id,
        )
    )).scalar_one()
    assert rec_db.opened_at is not None
    assert rec_db.clicked_at is not None

    # Verify Detail metrics updated
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{broadcast_id}", headers=auth_owner)
    d = detail_res.json()
    assert d["opened_count"] == 1
    assert d["open_rate"] == 100.0
    assert d["interest_count"] == 0
    assert d["rsvp_count"] == 0

    # 2. User expresses interest ('Хочу пойти')
    int_res = await client.post(f"/api/v1/events/{event_id}/interest", headers=auth_recipient)
    assert int_res.status_code == 200
    assert int_res.json()["is_interested"] is True

    # Verify interest attribution recorded
    await test_session.refresh(rec_db)
    assert rec_db.attributed_interest_at is not None

    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{broadcast_id}", headers=auth_owner)
    d = detail_res.json()
    assert d["interest_count"] == 1
    assert d["interest_conversion"] == 100.0

    # 3. User confirms RSVP ('Я иду')
    rsvp_res = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=auth_recipient)
    assert rsvp_res.status_code == 200
    assert rsvp_res.json()["is_attending"] is True

    # Verify RSVP attribution recorded
    await test_session.refresh(rec_db)
    assert rec_db.attributed_rsvp_at is not None

    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{broadcast_id}", headers=auth_owner)
    d = detail_res.json()
    assert d["rsvp_count"] == 1
    assert d["rsvp_conversion"] == 100.0


@pytest.mark.asyncio
async def test_attribution_security_unauthorized_user(client, test_session):
    """User who was NOT a broadcast recipient cannot have their view or actions attributed."""
    owner_id = 9003
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_sec')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Dance Studio", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Salsa Masterclass", 3),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Recipient user receives broadcast
    rec_uid = 9301
    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=rec_uid, username='dancer')}"},
    )

    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    token = res_bcast.json()["attribution_token"]
    bcast_id = res_bcast.json()["id"]

    # Outside user (NOT recipient) clicks link with the token
    outside_uid = 9302
    auth_outside = {"Authorization": f"tma {make_test_init_data(user_id=outside_uid, username='stranger')}"}

    view_res = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "broadcast", "broadcast_token": token},
        headers=auth_outside,
    )
    assert view_res.status_code == 200  # Non-blocking, event view succeeds!

    # But broadcast attribution is 0
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    assert detail_res.json()["opened_count"] == 0

    # Outside user RSVPs -> must NOT be attributed
    await client.post(f"/api/v1/events/{event_id}/rsvp", headers=auth_outside)
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    assert detail_res.json()["rsvp_count"] == 0


@pytest.mark.asyncio
async def test_no_false_attribution_across_different_events(client, test_session):
    """Broadcast for Event A must NEVER attribute views or actions on Event B."""
    owner_id = 9004
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_diff')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Multi Event Club", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    # Event A
    res_a = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Event A", 2),
        headers=auth_owner,
    )
    event_a_id = res_a.json()["id"]

    # Event B
    res_b = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Event B", 3),
        headers=auth_owner,
    )
    event_b_id = res_b.json()["id"]

    # Approve both
    for eid in (event_a_id, event_b_id):
        ev = (await test_session.execute(select(Event).where(Event.id == eid))).scalar_one()
        ev.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Recipient
    rec_uid = 9401
    auth_rec = {"Authorization": f"tma {make_test_init_data(user_id=rec_uid, username='fan_ab')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_rec)

    # Broadcast for Event A
    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_a_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    token_a = res_bcast.json()["attribution_token"]
    bcast_a_id = res_bcast.json()["id"]

    # User views Event B with Event A's token
    view_res = await client.post(
        f"/api/v1/events/{event_b_id}/view",
        json={"source": "broadcast", "broadcast_token": token_a},
        headers=auth_rec,
    )
    assert view_res.status_code == 200

    # User RSVPs to Event B
    await client.post(f"/api/v1/events/{event_b_id}/rsvp", headers=auth_rec)

    # Broadcast A must NOT attribute any views or RSVPs from Event B
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_a_id}", headers=auth_owner)
    assert detail_res.json()["opened_count"] == 0
    assert detail_res.json()["rsvp_count"] == 0


@pytest.mark.asyncio
async def test_24h_attribution_window_expiration(client, test_session):
    """Actions occurring > 24 hours after broadcast creation must NOT be attributed."""
    owner_id = 9005
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_exp')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Window Club", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Time Event", 2),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    rec_uid = 9501
    auth_rec = {"Authorization": f"tma {make_test_init_data(user_id=rec_uid, username='late_user')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_rec)

    # Create broadcast
    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    token = res_bcast.json()["attribution_token"]
    bcast_id = res_bcast.json()["id"]

    # Artificially age the broadcast to 25 hours ago
    bcast_db = (await test_session.execute(select(Broadcast).where(Broadcast.id == bcast_id))).scalar_one()
    bcast_db.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
    await test_session.commit()

    # User attempts to view event with the aged broadcast token
    view_res = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "broadcast", "broadcast_token": token},
        headers=auth_rec,
    )
    assert view_res.status_code == 200

    # Must NOT be attributed
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    assert detail_res.json()["opened_count"] == 0


@pytest.mark.asyncio
async def test_no_attribution_pre_existing_interest_or_rsvp(client, test_session):
    """
    If a user already marked 'Хочу пойти' or 'Я иду' BEFORE the broadcast was created,
    that engagement was pre-existing and must NOT be attributed as a broadcast conversion.
    """
    owner_id = 9006
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_pre')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Loyal Audience Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Exclusive Meetup", 4),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # User 1 has PRE-EXISTING interest BEFORE broadcast
    u1_id = 9601
    auth_u1 = {"Authorization": f"tma {make_test_init_data(user_id=u1_id, username='pre_interest_user')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_u1)
    await client.post(f"/api/v1/events/{event_id}/interest", headers=auth_u1)

    # Explicitly set interest created_at to 10 minutes ago
    u1_db = (await test_session.execute(select(User).where(User.telegram_id == u1_id))).scalar_one()
    int_db = (await test_session.execute(
        select(EventInterest).where(EventInterest.event_id == event_id, EventInterest.user_id == u1_db.id)
    )).scalar_one()
    int_db.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await test_session.commit()

    # User 2 has PRE-EXISTING RSVP BEFORE broadcast
    u2_id = 9602
    auth_u2 = {"Authorization": f"tma {make_test_init_data(user_id=u2_id, username='pre_rsvp_user')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_u2)
    await client.post(f"/api/v1/events/{event_id}/rsvp", headers=auth_u2)

    u2_db = (await test_session.execute(select(User).where(User.telegram_id == u2_id))).scalar_one()
    att_db = (await test_session.execute(
        select(EventAttendee).where(EventAttendee.event_id == event_id, EventAttendee.user_id == u2_db.id)
    )).scalar_one()
    att_db.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await test_session.commit()

    # Now create broadcast
    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    token = res_bcast.json()["attribution_token"]
    bcast_id = res_bcast.json()["id"]

    # Both users open the event via the broadcast link
    for auth in (auth_u1, auth_u2):
        await client.post(
            f"/api/v1/events/{event_id}/view",
            json={"source": "broadcast", "broadcast_token": token},
            headers=auth,
        )

    # Check that opens are attributed (both opened via link)
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    assert detail_res.json()["opened_count"] == 2

    # User 1 toggles interest again
    await client.post(f"/api/v1/events/{event_id}/interest", headers=auth_u1)
    # User 2 re-confirms RSVP
    await client.post(f"/api/v1/events/{event_id}/rsvp", headers=auth_u2)

    # Conversions must remain 0 because their intent was pre-existing before broadcast
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    d = detail_res.json()
    assert d["interest_count"] == 0
    assert d["rsvp_count"] == 0
    assert d["interest_conversion"] == 0.0
    assert d["rsvp_conversion"] == 0.0


@pytest.mark.asyncio
async def test_afisha_views_zero_false_attribution(client, test_session):
    """Direct views from feed/afisha must NEVER attribute to any broadcast."""
    owner_id = 9007
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_afisha')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Afisha Event Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Afisha Event", 2),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Recipient receives broadcast
    rec_uid = 9701
    auth_rec = {"Authorization": f"tma {make_test_init_data(user_id=rec_uid, username='feed_browser')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_rec)

    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    bcast_id = res_bcast.json()["id"]

    # User opens event from Discovery/Afisha feed (no broadcast_token)
    await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "discovery"},
        headers=auth_rec,
    )
    await client.post(f"/api/v1/events/{event_id}/interest", headers=auth_rec)
    await client.post(f"/api/v1/events/{event_id}/rsvp", headers=auth_rec)

    # Zero attribution on the broadcast
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    d = detail_res.json()
    assert d["opened_count"] == 0
    assert d["interest_count"] == 0
    assert d["rsvp_count"] == 0


@pytest.mark.asyncio
async def test_organizer_list_and_detail_aggregate_privacy(client, test_session):
    """
    Organizer workspace endpoints must only return numeric aggregate counts and rates.
    Zero recipient lists, user IDs, or personal identifiers are exposed.
    """
    owner_id = 9008
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_priv')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Privacy Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Privacy Event", 2),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    rec_uid = 9801
    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=rec_uid, username='secret_user')}"},
    )

    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    bcast_id = res_bcast.json()["id"]

    # Verify List endpoint
    list_res = await client.get("/api/v1/organizer/broadcasts", headers=auth_owner)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    item = [x for x in items if x["id"] == bcast_id][0]

    # Required aggregate fields present
    for field in ("opened_count", "interest_count", "rsvp_count", "open_rate", "interest_conversion", "rsvp_conversion"):
        assert field in item
        assert isinstance(item[field], (int, float))

    # Forbidden fields absent
    assert "recipients" not in item
    assert "users" not in item

    # Verify Detail endpoint
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    assert detail_res.status_code == 200
    d = detail_res.json()
    for field in ("opened_count", "interest_count", "rsvp_count", "open_rate", "interest_conversion", "rsvp_conversion"):
        assert field in d
        assert isinstance(d[field], (int, float))
    assert "recipients" not in d
    assert "users" not in d


@pytest.mark.asyncio
async def test_zero_denominator_safety(client, test_session):
    """Broadcasts with delivered_count == 0 must return 0.0% conversion rates safely without ZeroDivisionError."""
    owner_id = 9009
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_zero')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Zero Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Zero Event", 2),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    rec_uid = 9901
    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=rec_uid, username='zero_user')}"},
    )

    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    bcast_id = res_bcast.json()["id"]

    # Manually simulate 0 delivered in database
    bcast_db = (await test_session.execute(select(Broadcast).where(Broadcast.id == bcast_id))).scalar_one()
    bcast_db.delivered_count = 0
    await test_session.commit()

    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    assert detail_res.status_code == 200
    d = detail_res.json()
    assert d["open_rate"] == 0.0
    assert d["interest_conversion"] == 0.0
    assert d["rsvp_conversion"] == 0.0


@pytest.mark.asyncio
async def test_broadcast_view_invalid_token_resilience(client, test_session):
    """Non-existent or malformed broadcast token never crashes or fails event view."""
    viewer_id = 9902
    auth_viewer = {"Authorization": f"tma {make_test_init_data(user_id=viewer_id, username='resilient_user')}"}

    # Create published event
    owner_id = 9010
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_res')}"}
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Resilient Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Resilient Event", 2),
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Pass non-existent token
    view_res = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "broadcast", "broadcast_token": "invalid_fake_token_123"},
        headers=auth_viewer,
    )
    assert view_res.status_code == 200
    assert view_res.json()["recorded"] is True


def test_startapp_deep_link_token_extraction_logic():
    """Validates the exact logic used in frontend processStartParam."""
    def parse_start_param(clean: str):
        if not clean:
            return None, None
        if clean.startswith("event_"):
            param_rest = clean[6:].split("?")[0].split("&")[0].split("#")[0].rstrip("/")
            if "_b_" in param_rest:
                parts = param_rest.split("_b_")
                return parts[0], parts[1] or None
            return param_rest, None
        return None, None

    # Full parameter with token
    eid, token = parse_start_param("event_3fa85f64-5717-4562-b3fc-2c963f66afa6_b_0123456789abcdef")
    assert eid == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    assert token == "0123456789abcdef"

    # Plain event parameter (no token)
    eid, token = parse_start_param("event_3fa85f64-5717-4562-b3fc-2c963f66afa6")
    assert eid == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    assert token is None

    # Trailing slash or query artifact
    eid, token = parse_start_param("event_3fa85f64-5717-4562-b3fc-2c963f66afa6_b_abcdef1234567890/?ref=tg")
    assert eid == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    assert token == "abcdef1234567890"

