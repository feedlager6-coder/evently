import pytest
import httpx
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from tests.conftest import make_test_init_data
from app.config import settings
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastType,
    BroadcastStatus,
    RecipientStatus,
)
from app.services.broadcast_service import dispatch_broadcast
from app.services.notification_service import (
    send_telegram_event_message,
    notify_event_updated,
    notify_event_cancelled,
)
from app.services.entitlement_service import EntitlementService


@pytest.mark.asyncio
async def test_d504_01_single_dispatch_single_send(test_session):
    """1. Single broadcast dispatch produces exactly 1 send per recipient."""
    u1 = User(telegram_id=504101, username="user1")
    u2 = User(telegram_id=504102, username="user2")
    test_session.add_all([u1, u2])
    await test_session.commit()

    org = Organization(
        id="d504-org-1",
        owner_user_id=u1.id,
        name="D504 Org 1",
        slug="d504-org-1",
        category="Культура",
    )
    test_session.add(org)
    await test_session.commit()

    broadcast = Broadcast(
        id="bc-d504-1",
        organization_id=org.id,
        created_by_user_id=u1.id,
        broadcast_type=BroadcastType.MARKETING.value,
        target_type="organization_subscribers",
        template_key="custom_update",
        status=BroadcastStatus.QUEUED.value,
        custom_text="Test message",
    )
    test_session.add(broadcast)
    await test_session.commit()

    r1 = BroadcastRecipient(
        broadcast_id=broadcast.id,
        user_id=u1.id,
        status=RecipientStatus.PENDING.value,
    )
    r2 = BroadcastRecipient(
        broadcast_id=broadcast.id,
        user_id=u2.id,
        status=RecipientStatus.PENDING.value,
    )
    test_session.add_all([r1, r2])
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 999}}
    mock_client.post.return_value = mock_resp

    res = await dispatch_broadcast(test_session, broadcast.id, http_client=mock_client)

    assert res.status == BroadcastStatus.COMPLETED.value
    assert res.sent_count == 2
    assert res.failed_count == 0
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_d504_02_concurrent_dispatch_idempotency_locking(test_session):
    """2. Concurrent/repeated dispatch does not duplicate sends due to atomic status locking."""
    u1 = User(telegram_id=504201, username="user20")
    test_session.add(u1)
    await test_session.commit()

    org = Organization(
        id="d504-org-2",
        owner_user_id=u1.id,
        name="D504 Org 2",
        slug="d504-org-2",
        category="Культура",
    )
    test_session.add(org)
    await test_session.commit()

    broadcast = Broadcast(
        id="bc-d504-2",
        organization_id=org.id,
        created_by_user_id=u1.id,
        broadcast_type=BroadcastType.MARKETING.value,
        target_type="organization_subscribers",
        template_key="custom_update",
        status=BroadcastStatus.QUEUED.value,
        custom_text="Idempotency test",
    )
    test_session.add(broadcast)
    await test_session.commit()

    r1 = BroadcastRecipient(
        broadcast_id=broadcast.id,
        user_id=u1.id,
        status=RecipientStatus.PENDING.value,
    )
    test_session.add(r1)
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 1000}}
    mock_client.post.return_value = mock_resp

    # First dispatch
    res1 = await dispatch_broadcast(test_session, broadcast.id, http_client=mock_client)
    assert res1.sent_count == 1
    assert mock_client.post.call_count == 1

    # Second dispatch of same broadcast (already completed/sent, recipient status is SENT)
    res2 = await dispatch_broadcast(test_session, broadcast.id, http_client=mock_client)
    # Should NOT send again
    assert mock_client.post.call_count == 1
    assert res2.sent_count == 1


@pytest.mark.asyncio
async def test_d504_03_photo_timeout_skips_text_fallback():
    """3. When sendPhoto raises TimeoutException, do NOT fallback to sendMessage."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.TimeoutException("Read timeout on sendPhoto")

    result = await send_telegram_event_message(
        client=mock_client,
        bot_token="test_bot_token",
        chat_id=12345678,
        text="Event test notification",
        reply_markup=None,
        image_url="https://example.com/cover.jpg",
    )

    # Must return False and NOT call sendMessage
    assert result is False
    # Only 1 attempt was made (sendPhoto) and NO fallback call to sendMessage
    assert mock_client.post.call_count == 1
    called_url = mock_client.post.call_args[0][0]
    assert "sendPhoto" in called_url


@pytest.mark.asyncio
async def test_d504_04_photo_http_400_does_fallback():
    """4. When sendPhoto returns HTTP 400 (bad image request), fallback to sendMessage."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    mock_bad_photo_resp = MagicMock()
    mock_bad_photo_resp.status_code = 400
    mock_bad_photo_resp.text = "Bad Request: wrong file identifier/HTTP URL specified"

    mock_good_msg_resp = MagicMock()
    mock_good_msg_resp.status_code = 200
    mock_good_msg_resp.json.return_value = {"ok": True}

    mock_client.post.side_effect = [mock_bad_photo_resp, mock_good_msg_resp]

    result = await send_telegram_event_message(
        client=mock_client,
        bot_token="test_bot_token",
        chat_id=12345678,
        text="Event test notification",
        reply_markup=None,
        image_url="https://example.com/bad-cover.jpg",
    )

    assert result is True
    assert mock_client.post.call_count == 2
    first_url = mock_client.post.call_args_list[0][0][0]
    second_url = mock_client.post.call_args_list[1][0][0]
    assert "sendPhoto" in first_url
    assert "sendMessage" in second_url


@pytest.mark.asyncio
async def test_d504_05_event_update_fields(client, test_session):
    """5. PATCH /api/v1/events/{id} updates all fields: title, description, category, city, date/time, venue, address."""
    user_id = 9501
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='event_organizer_5')}"}

    # Create Org
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "D504 Update Org", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Create Event
    res_create = await client.post(
        "/api/v1/events",
        json={
            "title": "Original Event Title",
            "description": "Original description",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "organization_id": org_id,
            "start_at": "2026-11-01T18:00:00Z",
            "venue_name": "Original Hall",
            "address": "Original Str 1",
            "is_free": True,
        },
        headers=auth,
    )
    assert res_create.status_code in (200, 201)
    ev_id = res_create.json()["id"]

    # Update event with PATCH
    res_patch = await client.patch(
        f"/api/v1/events/{ev_id}",
        json={
            "title": "Updated Event Title",
            "description": "Updated new description",
            "category_id": "exhibitions",
            "city_id": "kaspiysk",
            "start_at": "2026-11-02T19:30:00Z",
            "venue_name": "Updated New Hall",
            "address": "Updated Str 42",
        },
        headers=auth,
    )
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["title"] == "Updated Event Title"
    assert updated["description"] == "Updated new description"
    assert updated["category_id"] == "exhibitions"
    assert updated["city_id"] == "kaspiysk"
    assert updated["venue_name"] == "Updated New Hall"
    assert updated["address"] == "Updated Str 42"
    assert "2026-11-02T19:30:00" in updated["start_at"]


@pytest.mark.asyncio
async def test_d504_06_event_update_notifications_recipients(test_session):
    """6. notify_event_updated sends ONLY to confirmed attendees (EventAttendee); 0 to interest, 0 to subscribers."""
    u_attendee = User(telegram_id=504301, username="att_user")
    u_interested = User(telegram_id=504302, username="int_user")
    u_subscriber = User(telegram_id=504303, username="sub_user")
    test_session.add_all([u_attendee, u_interested, u_subscriber])
    await test_session.commit()

    org = Organization(
        id="d504-org-notif",
        owner_user_id=u_subscriber.id,
        name="Notif Org",
        slug="notif-org",
        category="Культура",
    )
    test_session.add(org)
    await test_session.commit()

    ev = Event(
        id="d504-ev-notif",
        title="Important Meeting",
        description="Detailed description for notification test 06",
        address="ул. Ленина, 10",
        organizer_user_id=u_subscriber.id,
        organization_id=org.id,
        category_id="concerts",
        city_id="makhachkala",
        venue_name="Main Stage",
        start_at=datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc),
        status="published",
    )
    test_session.add(ev)

    # User 1 is Attendee (RSVP)
    test_session.add(EventAttendee(event_id=ev.id, user_id=u_attendee.id))
    # User 2 is Interested (Хочу пойти)
    test_session.add(EventInterest(event_id=ev.id, user_id=u_interested.id))
    # User 3 is Subscriber to Org
    test_session.add(Subscription(organization_id=org.id, user_id=u_subscriber.id))
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_client.post.return_value = mock_resp

    sent_count = await notify_event_updated(
        event=ev,
        changes={"time_changed": True, "old_start_at": "18:00", "new_start_at": "19:00"},
        session=test_session,
        http_client=mock_client,
    )

    # Exactly 2 messages sent: to u_attendee (504301) and u_interested (504302); 0 to subscriber (504303)
    assert sent_count == 2
    assert mock_client.post.call_count == 2
    delivered_chats = {call[1]["json"]["chat_id"] for call in mock_client.post.call_args_list}
    assert delivered_chats == {504301, 504302}
    assert 504303 not in delivered_chats


@pytest.mark.asyncio
async def test_d504_07_event_cancel_notifications_recipients(test_session):
    """7. notify_event_cancelled sends to attendees + interested (deduplicated); 0 to subscribers."""
    u1 = User(telegram_id=504401, username="c1")
    u2 = User(telegram_id=504402, username="c2")
    u3 = User(telegram_id=504403, username="c3")  # subscriber only
    test_session.add_all([u1, u2, u3])
    await test_session.commit()

    org = Organization(
        id="d504-org-cancel",
        owner_user_id=u3.id,
        name="Cancel Org",
        slug="cancel-org",
        category="Культура",
    )
    test_session.add(org)
    await test_session.commit()

    ev = Event(
        id="d504-ev-cancel",
        title="Concert to Cancel",
        description="Detailed description for cancel test 07",
        address="ул. Ленина, 10",
        organizer_user_id=u3.id,
        organization_id=org.id,
        category_id="concerts",
        city_id="makhachkala",
        venue_name="Concert Hall",
        start_at=datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc),
        status="published",
    )
    test_session.add(ev)

    # u1 is BOTH attendee and interested
    test_session.add(EventAttendee(event_id=ev.id, user_id=u1.id))
    test_session.add(EventInterest(event_id=ev.id, user_id=u1.id))

    # u2 is interested only
    test_session.add(EventInterest(event_id=ev.id, user_id=u2.id))

    # u3 is subscriber only
    test_session.add(Subscription(organization_id=org.id, user_id=u3.id))
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

    # Exactly 2 messages sent (u1 deduplicated, u2 included, u3 excluded)
    assert sent_count == 2
    assert mock_client.post.call_count == 2
    delivered_chats = {call[1]["json"]["chat_id"] for call in mock_client.post.call_args_list}
    assert delivered_chats == {504401, 504402}


@pytest.mark.asyncio
async def test_d504_08_city_switch_preserves_relationships(client, test_session):
    """8. Switching cities never deletes or alters RSVP or Interest records."""
    user_id = 9801
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='city_switcher')}"}

    # Use seeded published event in SPb
    res_feed_init = await client.get("/api/v1/events?city_id=spb")
    assert res_feed_init.status_code == 200
    events = res_feed_init.json()["events"]
    assert len(events) >= 2
    ev_att = events[0]["id"]
    ev_int = events[1]["id"]

    # RSVP and Interest
    res_rsvp = await client.post(f"/api/v1/events/{ev_att}/rsvp", headers=auth)
    assert res_rsvp.status_code == 200
    res_int = await client.post(f"/api/v1/events/{ev_int}/interest", headers=auth)
    assert res_int.status_code == 200

    # User browses another city (e.g. Kaspiysk or Derbent)
    res_feed = await client.get("/api/v1/events?city_id=derbent", headers=auth)
    assert res_feed.status_code == 200

    # Verify relationships are preserved and not destroyed by browsing another city
    att_res = await client.get("/api/v1/users/me/events?type=attending", headers=auth)
    assert att_res.status_code == 200
    att_ids = [e["id"] for e in att_res.json()]
    assert ev_att in att_ids

    int_list_res = await client.get("/api/v1/users/me/events?type=interested", headers=auth)
    assert int_list_res.status_code == 200
    int_ids = [e["id"] for e in int_list_res.json()]
    assert ev_int in int_ids


@pytest.mark.asyncio
async def test_d504_09_pro_org_quota_starts_at_zero_and_limit_is_20(client, test_session):
    """9. Newly activated Pro organization starts at 0/20 broadcasts used, 20 remaining."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_d504')}"}
    user_id = 9901
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='pro_quota_owner')}"}

    # Create Org
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Fresh Pro Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Admin upgrades to Pro
    await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "status": "active"},
        headers=admin_auth,
    )

    # Check entitlements
    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent.status_code == 200
    ent = res_ent.json()
    assert ent["plan"] == "pro"
    assert ent["limits"]["broadcasts_used_this_month"] == 0
    assert ent["limits"]["broadcasts_remaining"] == 20
    assert ent["limits"]["broadcasts_per_month"] == 20


@pytest.mark.asyncio
async def test_d504_10_quota_counts_only_successful_marketing_broadcasts(test_session):
    """10. Failed broadcasts (0 sent), transactional broadcasts, and other orgs do NOT consume quota."""
    u = User(telegram_id=504501, username="q1")
    test_session.add(u)
    await test_session.commit()

    org_target = Organization(
        id="d504-org-quota-target",
        owner_user_id=u.id,
        name="Target Org",
        slug="target-org",
        category="Культура",
    )
    org_other = Organization(
        id="d504-org-quota-other",
        owner_user_id=u.id,
        name="Other Org",
        slug="other-org",
        category="Культура",
    )
    test_session.add_all([org_target, org_other])
    await test_session.commit()

    # 1. Successful marketing broadcast for target org -> counts (1)
    b_success = Broadcast(
        id="bc-success",
        organization_id=org_target.id,
        created_by_user_id=u.id,
        broadcast_type=BroadcastType.MARKETING.value,
        status=BroadcastStatus.COMPLETED.value,
        sent_count=10,
        custom_text="Valid broadcast",
    )

    # 2. Failed broadcast (sent_count=0) -> does NOT count
    b_failed = Broadcast(
        id="bc-failed",
        organization_id=org_target.id,
        created_by_user_id=u.id,
        broadcast_type=BroadcastType.MARKETING.value,
        status=BroadcastStatus.FAILED.value,
        sent_count=0,
        custom_text="Failed broadcast",
    )

    # 3. Transactional notification broadcast -> does NOT count
    b_trans = Broadcast(
        id="bc-trans",
        organization_id=org_target.id,
        created_by_user_id=u.id,
        broadcast_type="transactional",
        status=BroadcastStatus.COMPLETED.value,
        sent_count=50,
        custom_text="Transactional notice",
    )

    # 4. Broadcast for other org -> does NOT count
    b_other = Broadcast(
        id="bc-other",
        organization_id=org_other.id,
        created_by_user_id=u.id,
        broadcast_type=BroadcastType.MARKETING.value,
        status=BroadcastStatus.COMPLETED.value,
        sent_count=15,
        custom_text="Other org broadcast",
    )

    test_session.add_all([b_success, b_failed, b_trans, b_other])
    await test_session.commit()

    # Query usage for target org
    usage = await EntitlementService.get_monthly_broadcast_usage(test_session, org_target.id)
    assert usage == 1  # Only b_success counted!
