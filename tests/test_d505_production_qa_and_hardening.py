import pytest
import httpx
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.view import EventView
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastType,
    BroadcastTargetType,
    BroadcastTemplateKey,
    BroadcastStatus,
    RecipientStatus,
)
from app.services.broadcast_service import (
    calculate_audience,
    dispatch_broadcast,
    create_broadcast,
)
from app.schemas.broadcast import BroadcastCreateRequest
from app.services.notification_service import (
    send_telegram_event_message,
    notify_event_updated,
    notify_event_cancelled,
    notify_organization_subscribers,
)
from app.services.event_service import update_organizer_event
from app.schemas.event import EventUpdate
from app.services.entitlement_service import EntitlementService


# ==============================================================================
# ISSUE 1: PRO QUOTA & TEST MODE PERSISTENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_d505_01_pro_quota_lifecycle_and_test_toggle_persistence(client, test_session):
    """
    Issue 1:
    Verifies that Pro quota accounting preserves history across admin test toggles.
    1. Fresh Pro org -> 20/20 (0 used, 20 remaining)
    2. One broadcast -> 19/20 (1 used)
    3. Two broadcasts -> 18/20 (2 used)
    4. Revert to Free -> history preserved
    5. Re-enable Pro -> 18/20 (2 used) preserved
    6. Non-marketing / 0-sent / other org broadcasts do NOT consume quota
    """
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_d505')}"}
    user_id = 9911
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='pro_persistence_owner')}"}

    # Create Org
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Quota Persistence Org", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # 1. Admin activates Pro
    await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "status": "active"},
        headers=admin_auth,
    )
    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    ent = res_ent.json()
    assert ent["limits"]["broadcasts_used_this_month"] == 0
    assert ent["limits"]["broadcasts_remaining"] == 20

    # 2. Add 1 successful marketing broadcast
    u_owner = (await test_session.execute(select(User).where(User.telegram_id == user_id))).scalar_one()
    b1 = Broadcast(
        id="bc-d505-q1",
        organization_id=org_id,
        created_by_user_id=u_owner.id,
        broadcast_type=BroadcastType.MARKETING.value,
        status=BroadcastStatus.COMPLETED.value,
        sent_count=5,
        custom_text="Broadcast 1",
    )
    test_session.add(b1)
    await test_session.commit()

    usage1 = await EntitlementService.get_monthly_broadcast_usage(test_session, org_id)
    assert usage1 == 1

    res_ent2 = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent2.json()["limits"]["broadcasts_used_this_month"] == 1
    assert res_ent2.json()["limits"]["broadcasts_remaining"] == 19

    # 3. Add 2nd successful marketing broadcast
    b2 = Broadcast(
        id="bc-d505-q2",
        organization_id=org_id,
        created_by_user_id=u_owner.id,
        broadcast_type=BroadcastType.MARKETING.value,
        status=BroadcastStatus.COMPLETED.value,
        sent_count=12,
        custom_text="Broadcast 2",
    )
    test_session.add(b2)
    await test_session.commit()

    usage2 = await EntitlementService.get_monthly_broadcast_usage(test_session, org_id)
    assert usage2 == 2

    # 4. Admin toggles org to Free (disables Pro)
    await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "free", "status": "active"},
        headers=admin_auth,
    )
    res_ent_free = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent_free.json()["plan"] == "free"

    # 5. Admin re-enables Pro
    await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "status": "active"},
        headers=admin_auth,
    )
    res_ent_repro = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent_repro.json()["plan"] == "pro"
    # History preserved: 2 used, 18 remaining
    assert res_ent_repro.json()["limits"]["broadcasts_used_this_month"] == 2
    assert res_ent_repro.json()["limits"]["broadcasts_remaining"] == 18

    # 6. Failed send (0 sent) and transactional broadcasts do NOT consume quota
    b_failed = Broadcast(
        id="bc-d505-qfail",
        organization_id=org_id,
        created_by_user_id=u_owner.id,
        broadcast_type=BroadcastType.MARKETING.value,
        status=BroadcastStatus.FAILED.value,
        sent_count=0,
        custom_text="Zero delivered",
    )
    b_trans = Broadcast(
        id="bc-d505-qtrans",
        organization_id=org_id,
        created_by_user_id=u_owner.id,
        broadcast_type="transactional",
        status=BroadcastStatus.COMPLETED.value,
        sent_count=100,
        custom_text="Service notice",
    )
    test_session.add_all([b_failed, b_trans])
    await test_session.commit()

    usage_final = await EntitlementService.get_monthly_broadcast_usage(test_session, org_id)
    assert usage_final == 2  # Still exactly 2!


# ==============================================================================
# ISSUE 2: EVENT UPDATE NOTIFICATION RECIPIENT ISOLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_d505_02_event_update_notifications_recipients(test_session):
    """
    Issue 2:
    When date/time or venue/address changes:
    - User A = RSVP ("Я иду") -> NOTIFIED
    - User B = Interest ("Хочу пойти") -> NOTIFIED
    - User C = Passive viewer (EventView) -> NO
    - User D = Organization subscriber only -> NO
    - User E = Different city user with RSVP -> NOTIFIED
    - User F = Different city user without relationship -> NO
    """
    ua = User(telegram_id=505101, username="ua_rsvp", default_city_id="makhachkala")
    ub = User(telegram_id=505102, username="ub_interest", default_city_id="makhachkala")
    uc = User(telegram_id=505103, username="uc_view", default_city_id="makhachkala")
    ud = User(telegram_id=505104, username="ud_sub", default_city_id="makhachkala")
    ue = User(telegram_id=505105, username="ue_diffcity_rsvp", default_city_id="moscow")
    uf = User(telegram_id=505106, username="uf_diffcity_none", default_city_id="moscow")
    test_session.add_all([ua, ub, uc, ud, ue, uf])
    await test_session.commit()

    org = Organization(
        id="d505-org-notif",
        owner_user_id=ud.id,
        name="Update Notif Org",
        slug="update-notif-org",
        category="Концерты",
        city_id="makhachkala",
    )
    test_session.add(org)
    await test_session.commit()

    ev = Event(
        id="d505-ev-update",
        title="Masterclass D505",
        description="Detailed description for event update test",
        address="ул. Пушкина, 5",
        venue_name="Concert Hall A",
        start_at=datetime(2026, 12, 1, 18, 0, tzinfo=timezone.utc),
        category_id="concerts",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=ud.id,
        status="published",
    )
    test_session.add(ev)

    # Relationships
    test_session.add(EventAttendee(event_id=ev.id, user_id=ua.id))
    test_session.add(EventInterest(event_id=ev.id, user_id=ub.id))
    test_session.add(EventView(event_id=ev.id, user_id=uc.id, source="feed"))
    test_session.add(Subscription(organization_id=org.id, user_id=ud.id))
    test_session.add(EventAttendee(event_id=ev.id, user_id=ue.id))
    # uf has no relationship
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_client.post.return_value = mock_resp

    sent_count = await notify_event_updated(
        event=ev,
        changes={
            "time_changed": True,
            "old_start_at": "18:00",
            "new_start_at": "19:30",
        },
        session=test_session,
        http_client=mock_client,
    )

    # Exactly 3 sent: ua (505101), ub (505102), ue (505105)
    assert sent_count == 3
    assert mock_client.post.call_count == 3
    delivered_chats = {call[1]["json"]["chat_id"] for call in mock_client.post.call_args_list}
    assert delivered_chats == {505101, 505102, 505105}
    # uc (viewer), ud (org subscriber only), uf (unrelated) are NOT notified
    assert 505103 not in delivered_chats
    assert 505104 not in delivered_chats
    assert 505106 not in delivered_chats


@pytest.mark.asyncio
async def test_d505_03_event_update_service_triggers_only_on_meaningful_changes(test_session):
    """
    Issue 2:
    Editing title/description/category or saving without changes does NOT trigger notify_event_updated.
    """
    u_owner = User(telegram_id=505201, username="ev_owner")
    u_att = User(telegram_id=505202, username="ev_att")
    test_session.add_all([u_owner, u_att])
    await test_session.commit()

    ev = Event(
        id="d505-ev-service-update",
        title="Initial Title",
        description="Initial description",
        address="ул. Горького, 1",
        venue_name="Initial Venue",
        start_at=datetime(2026, 12, 10, 19, 0, tzinfo=timezone.utc),
        category_id="concerts",
        city_id="makhachkala",
        organizer_user_id=u_owner.id,
        status="published",
    )
    test_session.add(ev)
    test_session.add(EventAttendee(event_id=ev.id, user_id=u_att.id))
    await test_session.commit()

    # 1. Update only title and description (no time/venue change)
    updated_ev, changes = await update_organizer_event(
        session=test_session,
        event_id=ev.id,
        user_id=u_owner.id,
        data=EventUpdate(title="New Cosmetic Title", description="New cosmetic description"),
    )
    assert "time_changed" not in changes
    assert "venue_changed" not in changes

    # 2. Update start_at with timezone awareness -> triggers time_changed
    updated_ev2, changes2 = await update_organizer_event(
        session=test_session,
        event_id=ev.id,
        user_id=u_owner.id,
        data=EventUpdate(start_at=datetime(2026, 12, 10, 20, 0, tzinfo=timezone.utc)),
    )
    assert changes2.get("time_changed") is True
    assert "2026-12-10 20:00:00" in str(updated_ev2.start_at)


# ==============================================================================
# ISSUE 3: EVENT INTEREST BROADCAST AUDIENCE & DELIVERY
# ==============================================================================

@pytest.mark.asyncio
async def test_d505_04_event_interest_two_recipients_both_delivered(test_session):
    """
    Issue 3:
    Reproduces production scenario:
    - User 1 (organizer) has Interest ('Хочу пойти')
    - User 2 (second account) has Interest ('Хочу пойти')
    Audience calculation: 2 eligible users
    Broadcast delivery: exactly 2 BroadcastRecipient records, 2 deliveries.
    Neither is excluded.
    """
    u_org = User(telegram_id=505301, username="org_user")
    u_guest = User(telegram_id=505302, username="guest_user")
    test_session.add_all([u_org, u_guest])
    await test_session.commit()

    org = Organization(
        id="d505-org-int-bc",
        owner_user_id=u_org.id,
        name="Interest Broadcast Org",
        slug="int-bc-org",
        category="Концерты",
        city_id="makhachkala",
    )
    test_session.add(org)
    await test_session.commit()

    ev = Event(
        id="d505-ev-int-bc",
        title="Event with 2 Interests",
        description="Description for 2 interest users test",
        address="ул. Ленина, 20",
        venue_name="Live Stage",
        start_at=datetime(2026, 11, 20, 19, 0, tzinfo=timezone.utc),
        category_id="concerts",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=u_org.id,
        status="published",
    )
    test_session.add(ev)
    # Both users have EventInterest
    test_session.add(EventInterest(event_id=ev.id, user_id=u_org.id))
    test_session.add(EventInterest(event_id=ev.id, user_id=u_guest.id))
    await test_session.commit()

    # 1. Calculate audience
    calc = await calculate_audience(
        session=test_session,
        organizer_user_id=u_org.id,
        organization_id=org.id,
        target_type=BroadcastTargetType.EVENT_INTEREST.value,
        broadcast_type=BroadcastType.MARKETING.value,
        event_id=ev.id,
    )
    assert calc["total_audience"] == 2
    assert len(calc["eligible_user_ids"]) == 2
    assert set(calc["eligible_user_ids"]) == {u_org.id, u_guest.id}

    # 2. Create and dispatch broadcast
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 881}}
    mock_client.post.return_value = mock_resp

    broadcast = Broadcast(
        id="bc-d505-two-int",
        organization_id=org.id,
        created_by_user_id=u_org.id,
        event_id=ev.id,
        target_type=BroadcastTargetType.EVENT_INTEREST.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        status=BroadcastStatus.QUEUED.value,
        custom_text="Special announcement for interested guests!",
    )
    test_session.add(broadcast)
    await test_session.commit()

    # Add recipients from eligible IDs
    for uid in calc["eligible_user_ids"]:
        test_session.add(BroadcastRecipient(
            broadcast_id=broadcast.id,
            user_id=uid,
            status=RecipientStatus.PENDING.value,
        ))
    await test_session.commit()

    res = await dispatch_broadcast(test_session, broadcast.id, http_client=mock_client)
    assert res.status == BroadcastStatus.COMPLETED.value
    assert res.sent_count == 2
    assert res.failed_count == 0
    assert mock_client.post.call_count == 2
    delivered_chats = {call[1]["json"]["chat_id"] for call in mock_client.post.call_args_list}
    assert delivered_chats == {505301, 505302}


@pytest.mark.asyncio
async def test_d505_05_event_interest_five_recipients_and_deduplication(test_session):
    """
    Issue 3:
    5 interest users -> 5 recipients.
    Scoped anti-fatigue does NOT block users because an unrelated organization sent a broadcast.
    """
    users = []
    for i in range(1, 6):
        u = User(telegram_id=505310 + i, username=f"guest_{i}")
        users.append(u)
    test_session.add_all(users)
    await test_session.commit()

    org = Organization(
        id="d505-org-int-5",
        owner_user_id=users[0].id,
        name="Five Users Org",
        slug="five-users-org",
        category="Культура",
        city_id="makhachkala",
    )
    test_session.add(org)
    await test_session.commit()

    ev = Event(
        id="d505-ev-int-5",
        title="Event with 5 Interests",
        description="Detailed description for 5 interests",
        address="ул. Мира, 1",
        venue_name="Concert Hall 5",
        start_at=datetime(2026, 11, 25, 20, 0, tzinfo=timezone.utc),
        category_id="concerts",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=users[0].id,
        status="published",
    )
    test_session.add(ev)
    for u in users:
        test_session.add(EventInterest(event_id=ev.id, user_id=u.id))
    await test_session.commit()

    calc = await calculate_audience(
        session=test_session,
        organizer_user_id=users[0].id,
        organization_id=org.id,
        target_type=BroadcastTargetType.EVENT_INTEREST.value,
        broadcast_type=BroadcastType.MARKETING.value,
        event_id=ev.id,
    )
    assert calc["total_audience"] == 5
    assert len(calc["eligible_user_ids"]) == 5


# ==============================================================================
# ISSUE 8: EVENT CANCELLATION NOTIFICATION RECIPIENT ISOLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_d505_06_event_cancellation_mixed_city_recipients(test_session):
    """
    Issue 8:
    Event in City A (Makhachkala).
    U1: City A + RSVP -> YES
    U2: City A + Interest -> YES
    U3: City A + View only -> NO
    U4: City A + Org subscription only -> NO
    U5: City B (Moscow) + RSVP -> YES
    U6: City B (Moscow) + no relationship -> NO
    """
    u1 = User(telegram_id=505401, username="u1_rsvp", default_city_id="makhachkala")
    u2 = User(telegram_id=505402, username="u2_int", default_city_id="makhachkala")
    u3 = User(telegram_id=505403, username="u3_view", default_city_id="makhachkala")
    u4 = User(telegram_id=505404, username="u4_sub", default_city_id="makhachkala")
    u5 = User(telegram_id=505405, username="u5_diffcity_rsvp", default_city_id="moscow")
    u6 = User(telegram_id=505406, username="u6_diffcity_none", default_city_id="moscow")
    test_session.add_all([u1, u2, u3, u4, u5, u6])
    await test_session.commit()

    org = Organization(
        id="d505-org-cancel",
        owner_user_id=u4.id,
        name="Cancel Mixed City Org",
        slug="cancel-mixed-org",
        category="Культура",
        city_id="makhachkala",
    )
    test_session.add(org)
    await test_session.commit()

    ev = Event(
        id="d505-ev-cancel-mixed",
        title="Event to Cancel",
        description="Cancel event description",
        address="ул. Ленина, 10",
        venue_name="Old Stage",
        start_at=datetime(2026, 12, 15, 18, 0, tzinfo=timezone.utc),
        category_id="concerts",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=u4.id,
        status="published",
    )
    test_session.add(ev)

    test_session.add(EventAttendee(event_id=ev.id, user_id=u1.id))
    test_session.add(EventInterest(event_id=ev.id, user_id=u2.id))
    test_session.add(EventView(event_id=ev.id, user_id=u3.id, source="feed"))
    test_session.add(Subscription(organization_id=org.id, user_id=u4.id))
    test_session.add(EventAttendee(event_id=ev.id, user_id=u5.id))
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_client.post.return_value = mock_resp

    sent_count = await notify_event_cancelled(
        event=ev,
        session=test_session,
        http_client=mock_client,
    )

    # Exactly 3 recipients: u1 (505401), u2 (505402), u5 (505405)
    assert sent_count == 3
    assert mock_client.post.call_count == 3
    delivered_chats = {call[1]["json"]["chat_id"] for call in mock_client.post.call_args_list}
    assert delivered_chats == {505401, 505402, 505405}
    assert 505403 not in delivered_chats
    assert 505404 not in delivered_chats
    assert 505406 not in delivered_chats


# ==============================================================================
# ISSUE 9: CITY SWITCH DOES NOT DESTROY EXPLICIT RELATIONSHIPS
# ==============================================================================

@pytest.mark.asyncio
async def test_d505_07_city_switch_preserves_relationships_and_notifications(client, test_session):
    """
    Issue 9:
    User RSVPs to Event in SPb, then browses another city (Derbent).
    Relationship remains in database and event update notification is still delivered to user.
    """
    user_id = 9812
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='city_switch_user')}"}

    # Fetch event in SPb
    res_feed = await client.get("/api/v1/events?city_id=spb")
    assert res_feed.status_code == 200
    events = res_feed.json()["events"]
    assert len(events) >= 1
    target_event_id = events[0]["id"]

    # RSVP to event
    res_rsvp = await client.post(f"/api/v1/events/{target_event_id}/rsvp", headers=auth)
    assert res_rsvp.status_code == 200

    # Switch discovery to Derbent
    res_switch = await client.get("/api/v1/events?city_id=derbent", headers=auth)
    assert res_switch.status_code == 200

    # Verify user personal attending list still has the SPb event
    res_me = await client.get("/api/v1/users/me/events?type=attending", headers=auth)
    assert res_me.status_code == 200
    att_ids = [e["id"] for e in res_me.json()]
    assert target_event_id in att_ids


# ==============================================================================
# ISSUE 11: BROADCAST PHOTO INTEGRITY & TIMEOUT SAFETY
# ==============================================================================

@pytest.mark.asyncio
async def test_d505_08_broadcast_photo_timeout_safety():
    """
    Issue 11:
    sendPhoto timeout NEVER triggers fallback text message (avoids duplicate send).
    sendPhoto HTTP 400 safely triggers fallback text message.
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.TimeoutException("Read timeout on sendPhoto")

    # Timeout case: must return False and NOT call sendMessage
    result_timeout = await send_telegram_event_message(
        client=mock_client,
        bot_token="test_bot_token",
        chat_id=12345678,
        text="Event update notification",
        reply_markup=None,
        image_url="https://example.com/cover.jpg",
    )
    assert result_timeout is False
    assert mock_client.post.call_count == 1
    assert "sendPhoto" in mock_client.post.call_args[0][0]

    # HTTP 400 case: must fallback to sendMessage
    mock_client2 = AsyncMock(spec=httpx.AsyncClient)
    mock_400 = MagicMock()
    mock_400.status_code = 400
    mock_400.text = "Bad Request: wrong image"
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"ok": True}
    mock_client2.post.side_effect = [mock_400, mock_200]

    result_400 = await send_telegram_event_message(
        client=mock_client2,
        bot_token="test_bot_token",
        chat_id=12345678,
        text="Event update notification",
        reply_markup=None,
        image_url="https://example.com/bad.jpg",
    )
    assert result_400 is True
    assert mock_client2.post.call_count == 2
    assert "sendPhoto" in mock_client2.post.call_args_list[0][0][0]
    assert "sendMessage" in mock_client2.post.call_args_list[1][0][0]


# ==============================================================================
# ISSUE 12: ORGANIZATION NEW EVENT NOTIFICATION TO SUBSCRIBERS
# ==============================================================================

@pytest.mark.asyncio
async def test_d505_09_organization_new_event_notification_to_subscribers(test_session):
    """
    Issue 12:
    When an organization publishes a new event, notifications are sent to organization subscribers.
    Photo cover is included.
    """
    u_owner = User(telegram_id=505501, username="org_owner_12")
    u_sub = User(telegram_id=505502, username="org_sub_12")
    test_session.add_all([u_owner, u_sub])
    await test_session.commit()

    org = Organization(
        id="d505-org-new-ev",
        owner_user_id=u_owner.id,
        name="New Event Org",
        slug="new-ev-org",
        category="Театр",
        city_id="makhachkala",
    )
    test_session.add(org)
    await test_session.commit()

    test_session.add(Subscription(organization_id=org.id, user_id=u_sub.id, notifications_enabled=True))

    ev = Event(
        id="d505-ev-new-pub",
        title="Premier Performance",
        description="Detailed description for premier",
        address="ул. Горького, 10",
        venue_name="Drama Theater",
        start_at=datetime(2026, 12, 20, 19, 0, tzinfo=timezone.utc),
        category_id="theatre",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=u_owner.id,
        status="published",
        cover_image_url="https://ivently.up.railway.app/uploads/premier.jpg",
    )
    test_session.add(ev)
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_client.post.return_value = mock_resp

    sent_count = await notify_organization_subscribers(
        event_id=ev.id,
        session=test_session,
        http_client=mock_client,
    )
    assert sent_count == 1
    assert mock_client.post.call_count == 1
    call_payload = mock_client.post.call_args[1]["json"]
    assert call_payload["chat_id"] == 505502
    assert "Premier Performance" in (call_payload.get("caption") or call_payload.get("text"))
