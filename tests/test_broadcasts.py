import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.event import Event, EventStatus
from app.models.interest import EventInterest
from app.models.user import User
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastTargetType,
    BroadcastType,
    BroadcastTemplateKey,
    BroadcastStatus,
    RecipientStatus,
)
from app.services.broadcast_service import (
    calculate_audience,
    format_broadcast_content,
    dispatch_broadcast,
)
from app.services.notification_service import notify_organization_subscribers


@pytest.fixture(autouse=True)
def setup_broadcast_tests(monkeypatch):
    """Bypasses entitlement quota and capability check for D4 broadcast engine internal tests."""
    from app.services.entitlement_service import EntitlementService
    async def mock_check(session, org_id, capability):
        return True, "Allowed in test", None
    async def mock_enforce(session, org_id, broadcast_type="marketing"):
        return True
    async def mock_require(session, org_id, capability):
        return True
    async def mock_enforce(session, org_id, broadcast_type="marketing"):
        return True
    monkeypatch.setattr(EntitlementService, "require_entitlement", mock_require)
    monkeypatch.setattr(EntitlementService, "enforce_broadcast_capacity", mock_enforce)
@pytest.mark.asyncio
async def test_organization_subscriber_audience_calculation(client, test_session):
    """Requirement 1: Organization subscriber audience calculation."""
    owner_id = 1101
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_calc')}"}

    # Create org
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Cinema Club", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    # 3 users subscribe
    for uid in (1201, 1202, 1203):
        h = {"Authorization": f"tma {make_test_init_data(user_id=uid, username=f'sub_{uid}')}"}
        sub_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=h)
        assert sub_res.status_code == 200

    # Preview broadcast for organization subscribers
    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Привет подписчикам!"
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 200
    data = preview_res.json()
    assert data["total_audience"] == 3
    assert data["eligible_recipients"] == 3
    assert data["disabled_notifications_count"] == 0
    assert data["fatigued_recipients_count"] == 0
    assert "Привет подписчикам!" in data["preview_text"]


@pytest.mark.asyncio
async def test_notifications_enabled_filtering(client, test_session):
    """Requirement 2: notifications_enabled filtering (disabled notifications excluded)."""
    owner_id = 1102
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_notif')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Art Gallery", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    # User 1 subscribes (active)
    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=1301, username='active_sub')}"}
    )

    # User 2 subscribes then disables notifications
    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=1302, username='muted_sub')}"}
    )
    u2 = (await test_session.execute(select(User).where(User.telegram_id == 1302))).scalar_one()
    sub2 = (await test_session.execute(
        select(Subscription).where(Subscription.user_id == u2.id, Subscription.organization_id == org_id)
    )).scalar_one()
    sub2.notifications_enabled = False
    await test_session.commit()

    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Новая выставка"
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 200
    data = preview_res.json()
    assert data["total_audience"] == 2
    assert data["eligible_recipients"] == 1
    assert data["disabled_notifications_count"] == 1


@pytest.mark.asyncio
async def test_unauthorized_organization_access(client, test_session):
    """Requirement 3: Unauthorized organization access returns 403."""
    owner_id = 1103
    hacker_id = 1104
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='legit_owner')}"}
    auth_hacker = {"Authorization": f"tma {make_test_init_data(user_id=hacker_id, username='hacker')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Private Club", "category": "Клуб", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    # Hacker tries to preview
    prev_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Spam"
        },
        headers=auth_hacker
    )
    assert prev_res.status_code == 403

    # Hacker tries to create broadcast
    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Spam"
        },
        headers=auth_hacker
    )
    assert create_res.status_code == 403


@pytest.mark.asyncio
async def test_event_interest_audience_restrictions(client, test_session):
    """Requirement 4: Event-interest audience restrictions."""
    owner_id = 1105
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_interest')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Rock Bar", "category": "Бар", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    # Create event
    ev_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Rock Night",
            "description": "Heavy metal live",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": "2026-10-10T19:00:00Z",
            "venue_name": "Rock Bar Hall",
            "organization_id": org_id
        },
        headers=auth_owner
    )
    event_id = ev_res.json()["id"]

    # User 1 marks interest ("Хочу пойти")
    user1_init = make_test_init_data(user_id=1401, username="rock_fan")
    await client.post(
        f"/api/v1/events/{event_id}/interest",
        headers={"Authorization": f"tma {user1_init}"}
    )

    # User 2 subscribes to org but does not mark interest on this event
    user2_init = make_test_init_data(user_id=1402, username="org_sub_only")
    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {user2_init}"}
    )

    # Preview event_interest audience for this event
    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "event_interest",
            "broadcast_type": "marketing",
            "template_key": "event_update",
            "event_id": event_id,
            "custom_text": "Двери открываются в 18:30"
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 200
    data = preview_res.json()
    assert data["total_audience"] == 1
    assert data["eligible_recipients"] == 1
    assert data["event_id"] == event_id

    # Trying event_interest without event_id must fail
    fail_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "event_interest",
            "broadcast_type": "marketing",
            "template_key": "event_update",
        },
        headers=auth_owner
    )
    assert fail_res.status_code == 400


@pytest.mark.asyncio
async def test_event_viewer_audience_rejection(client, test_session):
    """Requirement 5: Event-viewer audience rejection."""
    owner_id = 1106
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_viewers')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Drama Theater", "category": "Театр", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "event_viewers",
            "broadcast_type": "marketing",
            "template_key": "custom_update"
        },
        headers=auth_owner
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_past_attendee_only_audience_rejection(client, test_session):
    """Requirement 6: Past-attendee-only audience rejection."""
    owner_id = 1107
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_attendees')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Comedy Stage", "category": "Театр", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "past_attendees",
            "broadcast_type": "marketing",
            "template_key": "custom_update"
        },
        headers=auth_owner
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_broadcast_creation_and_persistence(client, test_session):
    """Requirement 7: Broadcast creation and recipient persistence."""
    owner_id = 1108
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_create')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Jazz Hall", "category": "Концертная площадка", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    # 2 subscribers
    for uid in (1501, 1502):
        await client.post(
            f"/api/v1/organizations/{org_id}/subscribe",
            headers={"Authorization": f"tma {make_test_init_data(user_id=uid, username=f'sub_{uid}')}"}
        )

    # Create broadcast
    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Особый вечер для подписчиков"
        },
        headers=auth_owner
    )
    assert create_res.status_code == 200
    data = create_res.json()
    broadcast_id = data["id"]
    assert data["total_recipients"] == 2
    assert data["sent_count"] == 2
    assert data["status"] == "completed"

    # Verify database persistence
    bcast_db = (await test_session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))).scalar_one()
    assert bcast_db.organization_id == org_id
    assert bcast_db.total_recipients == 2

    recipients_db = (await test_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.broadcast_id == broadcast_id)
    )).scalars().all()
    assert len(recipients_db) == 2
    assert all(r.status == RecipientStatus.SENT.value for r in recipients_db)


@pytest.mark.asyncio
async def test_broadcast_authorization(client, test_session):
    """Requirement 8: Broadcast authorization (only owner can view details)."""
    owner_id = 1109
    other_id = 1110
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_auth')}"}
    auth_other = {"Authorization": f"tma {make_test_init_data(user_id=other_id, username='other_org')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Book Club", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=1601, username='reader')}"}
    )

    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Читаем новую главу"
        },
        headers=auth_owner
    )
    bcast_id = create_res.json()["id"]

    # Owner can get details
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_owner)
    assert detail_res.status_code == 200

    # Other organizer cannot get details (403)
    unauth_res = await client.get(f"/api/v1/organizer/broadcasts/{bcast_id}", headers=auth_other)
    assert unauth_res.status_code == 403

    # Other organizer list does not include owner's broadcast
    list_res = await client.get("/api/v1/organizer/broadcasts", headers=auth_other)
    assert list_res.status_code == 200
    assert not any(b["id"] == bcast_id for b in list_res.json())


@pytest.mark.asyncio
async def test_idempotent_recipient_processing(client, test_session):
    """Requirement 9: Idempotent recipient processing (no duplicate sends)."""
    owner_id = 1111
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_idemp')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Art Space", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=1701, username='artist')}"}
    )

    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Открытие выставки"
        },
        headers=auth_owner
    )
    bcast_id = create_res.json()["id"]

    mock_client = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 999}}
    mock_client.post.return_value = mock_resp

    # Dispatch second time on already completed broadcast
    res = await dispatch_broadcast(test_session, bcast_id, http_client=mock_client)
    assert res.status == BroadcastStatus.COMPLETED.value
    # mock_client.post should NOT have been called because all recipients are already SENT!
    assert mock_client.post.call_count == 0


@pytest.mark.asyncio
async def test_telegram_403_handling(client, test_session):
    """Requirement 10: Telegram 403 handling (marks blocked & disables notifications)."""
    owner_id = 1112
    user_blocked_id = 1801
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_403')}"}
    auth_user = {"Authorization": f"tma {make_test_init_data(user_id=user_blocked_id, username='user_blocked')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Music Hub", "category": "Клуб", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    # User subscribes
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_user)

    # Resolve users from DB
    owner_user = (await test_session.execute(select(User).where(User.telegram_id == owner_id))).scalar_one()
    blocked_user = (await test_session.execute(select(User).where(User.telegram_id == user_blocked_id))).scalar_one()

    # Check notification enabled initially
    sub_init = (await test_session.execute(
        select(Subscription).where(Subscription.user_id == blocked_user.id, Subscription.organization_id == org_id)
    )).scalar_one()
    assert sub_init.notifications_enabled is True

    # Setup mock Telegram returning 403
    mock_client = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 403
    mock_resp.text = '{"ok":false,"error_code":403,"description":"Forbidden: bot was blocked by the user"}'
    mock_client.post.return_value = mock_resp

    broadcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_user.id,
        target_type="organization_subscribers",
        broadcast_type="marketing",
        template_key="custom_update",
        custom_text="Проверка 403",
        status=BroadcastStatus.QUEUED.value,
        total_recipients=1,
    )
    test_session.add(broadcast)
    await test_session.flush()

    rec = BroadcastRecipient(broadcast_id=broadcast.id, user_id=blocked_user.id, status=RecipientStatus.PENDING.value)
    test_session.add(rec)
    await test_session.commit()

    # Dispatch with mock 403 client
    bcast = await dispatch_broadcast(test_session, broadcast.id, http_client=mock_client)
    assert bcast.blocked_count == 1
    assert bcast.sent_count == 0
    assert bcast.status == BroadcastStatus.FAILED.value

    # Verify recipient status
    rec_db = (await test_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.broadcast_id == broadcast.id)
    )).scalar_one()
    assert rec_db.status == RecipientStatus.BLOCKED.value
    assert rec_db.error_code == "403"

    # Verify Subscription.notifications_enabled was auto-disabled!
    sub_after = (await test_session.execute(
        select(Subscription).where(Subscription.user_id == blocked_user.id, Subscription.organization_id == org_id)
    )).scalar_one()
    assert sub_after.notifications_enabled is False


@pytest.mark.asyncio
async def test_telegram_429_retry_handling(client, test_session):
    """Requirement 11: Telegram 429 retry handling with retry_after."""
    owner_id = 1113
    user_id = 1901
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_429')}"}
    auth_user = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='user_429')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Speedway", "category": "Спорт", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_user)

    owner_user = (await test_session.execute(select(User).where(User.telegram_id == owner_id))).scalar_one()
    sub_user = (await test_session.execute(select(User).where(User.telegram_id == user_id))).scalar_one()

    broadcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_user.id,
        target_type="organization_subscribers",
        broadcast_type="marketing",
        template_key="custom_update",
        status=BroadcastStatus.QUEUED.value,
        total_recipients=1,
    )
    test_session.add(broadcast)
    await test_session.flush()

    rec = BroadcastRecipient(broadcast_id=broadcast.id, user_id=sub_user.id, status=RecipientStatus.PENDING.value)
    test_session.add(rec)
    await test_session.commit()

    # Mock client: first call returns 429 with retry_after 0.01, second call returns 200
    mock_client = AsyncMock()
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.json.return_value = {"ok": False, "parameters": {"retry_after": 0.01}}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"ok": True, "result": {"message_id": 429200}}

    mock_client.post.side_effect = [resp_429, resp_200]

    bcast = await dispatch_broadcast(test_session, broadcast.id, http_client=mock_client)
    assert bcast.sent_count == 1
    assert bcast.status == BroadcastStatus.COMPLETED.value
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_failed_recipient_does_not_abort_campaign(client, test_session):
    """Requirement 12: Failed recipient does not stop campaign for other recipients."""
    owner_id = 1114
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_resilient')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Multi Space", "category": "Другое", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    for uid in (2101, 2102):
        await client.post(
            f"/api/v1/organizations/{org_id}/subscribe",
            headers={"Authorization": f"tma {make_test_init_data(user_id=uid, username=f'user_{uid}')}"}
        )

    owner_user = (await test_session.execute(select(User).where(User.telegram_id == owner_id))).scalar_one()
    u1 = (await test_session.execute(select(User).where(User.telegram_id == 2101))).scalar_one()
    u2 = (await test_session.execute(select(User).where(User.telegram_id == 2102))).scalar_one()

    broadcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_user.id,
        target_type="organization_subscribers",
        broadcast_type="marketing",
        template_key="custom_update",
        status=BroadcastStatus.QUEUED.value,
        total_recipients=2,
    )
    test_session.add(broadcast)
    await test_session.flush()

    rec1 = BroadcastRecipient(broadcast_id=broadcast.id, user_id=u1.id, status=RecipientStatus.PENDING.value)
    rec2 = BroadcastRecipient(broadcast_id=broadcast.id, user_id=u2.id, status=RecipientStatus.PENDING.value)
    test_session.add_all([rec1, rec2])
    await test_session.commit()

    # Recipient 1 returns 500, Recipient 2 returns 200
    mock_client = AsyncMock()
    resp_err = MagicMock()
    resp_err.status_code = 500
    resp_err.text = "Internal Telegram Error"

    resp_ok = MagicMock()
    resp_ok.status_code = 200
    resp_ok.json.return_value = {"ok": True, "result": {"message_id": 555}}

    mock_client.post.side_effect = [resp_err, resp_ok]

    bcast = await dispatch_broadcast(test_session, broadcast.id, http_client=mock_client)
    assert bcast.failed_count == 1
    assert bcast.sent_count == 1
    assert bcast.status == BroadcastStatus.PARTIALLY_FAILED.value


@pytest.mark.asyncio
async def test_marketing_fatigue_limit(client, test_session):
    """Requirement 13: Marketing fatigue limit (rolling 24-hour limit for marketing broadcasts)."""
    owner_id = 1115
    user_id = 2201
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_fatigue')}"}
    auth_user = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='user_fatigue')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Daily Cafe", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_user)

    owner_user = (await test_session.execute(select(User).where(User.telegram_id == owner_id))).scalar_one()
    sub_user = (await test_session.execute(select(User).where(User.telegram_id == user_id))).scalar_one()

    # 1. Send first marketing broadcast
    bcast1 = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_user.id,
        target_type="organization_subscribers",
        broadcast_type="marketing",
        template_key="custom_update",
        status=BroadcastStatus.COMPLETED.value,
        total_recipients=1,
        sent_count=1,
    )
    test_session.add(bcast1)
    await test_session.flush()

    rec1 = BroadcastRecipient(
        broadcast_id=bcast1.id,
        user_id=sub_user.id,
        status=RecipientStatus.SENT.value,
        sent_at=datetime.now(timezone.utc) - timedelta(hours=2)  # sent 2 hours ago
    )
    test_session.add(rec1)
    await test_session.commit()

    # 2. Preview second marketing broadcast -> user must be excluded due to fatigue
    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Второй маркетинг за день"
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 200
    data = preview_res.json()
    assert data["total_audience"] == 1
    assert data["eligible_recipients"] == 0
    assert data["fatigued_recipients_count"] == 1


@pytest.mark.asyncio
async def test_transactional_notification_not_blocked_by_marketing_fatigue(client, test_session):
    """Requirement 14: Transactional notifications are NOT blocked by marketing fatigue."""
    owner_id = 1116
    user_id = 2301
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_trans')}"}
    auth_user = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='user_trans')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Concert Hall", "category": "Концертная площадка", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_user)

    owner_user = (await test_session.execute(select(User).where(User.telegram_id == owner_id))).scalar_one()
    sub_user = (await test_session.execute(select(User).where(User.telegram_id == user_id))).scalar_one()

    # User received a marketing message 1 hour ago
    bcast_mkt = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_user.id,
        target_type="organization_subscribers",
        broadcast_type="marketing",
        template_key="custom_update",
        status=BroadcastStatus.COMPLETED.value,
        total_recipients=1,
        sent_count=1,
    )
    test_session.add(bcast_mkt)
    await test_session.flush()

    rec_mkt = BroadcastRecipient(
        broadcast_id=bcast_mkt.id,
        user_id=sub_user.id,
        status=RecipientStatus.SENT.value,
        sent_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    test_session.add(rec_mkt)
    await test_session.commit()

    # 1. Manual transactional via API is blocked (anti-abuse rule)
    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "transactional",
            "template_key": "custom_update",
            "custom_text": "Внимание! Время концерта перенесено."
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 400

    # 2. System-level audience calculation correctly exempts transactional notifications from marketing fatigue
    data = await calculate_audience(
        session=test_session,
        organizer_user_id=owner_user.id,
        organization_id=org_id,
        target_type="organization_subscribers",
        broadcast_type="transactional",
    )
    assert data["total_audience"] == 1
    # Transactional is NOT blocked!
    assert len(data["eligible_user_ids"]) == 1
    assert data["fatigued_recipients_count"] == 0


@pytest.mark.asyncio
async def test_zero_recipient_campaign(client, test_session):
    """Requirement 15: Zero-recipient campaign preview returns 0 and creation is rejected with 400."""
    owner_id = 1117
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_zero')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Empty Space", "category": "Другое", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    # Preview returns 0 eligible recipients
    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Тест"
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 200
    assert preview_res.json()["eligible_recipients"] == 0

    # Attempting to create broadcast with 0 recipients returns 400
    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Тест"
        },
        headers=auth_owner
    )
    assert create_res.status_code == 400
    assert "Нет доступных получателей" in create_res.json()["detail"]


@pytest.mark.asyncio
async def test_message_html_escaping(client, test_session):
    """Requirement 16: Safe message HTML escaping prevents injection or malformed HTML."""
    owner = Organization(
        id="org-test-escape",
        owner_user_id=1,
        name='Test & "Safe" <Club>',
        slug="test-safe-club",
        category="Клуб"
    )
    event = Event(
        id="ev-test-escape",
        title='<script>alert("XSS")</script> & Rock',
        venue_name="Venue <Hall> & Bar",
        start_at=datetime(2026, 10, 15, 20, 0, tzinfo=timezone.utc),
        organization_id=owner.id,
        organizer_user_id=1,
        category_id="concerts",
        city_id="makhachkala"
    )

    text, btn_text, btn_url = format_broadcast_content(
        organization=owner,
        template_key=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        event=event,
        custom_text='Внимание: <tag> & "quotes"'
    )

    # Verify no raw unescaped script or tag
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "&amp;" in text
    assert "&lt;tag&gt;" in text
    assert "Test &amp; &quot;Safe&quot; &lt;Club&gt;" in text


@pytest.mark.asyncio
async def test_existing_organization_publication_notifications_unchanged(client, test_session):
    """Requirement 17: Existing publication notification dispatch remains completely intact."""
    owner_id = 1118
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_pub')}"}
    auth_admin = {"Authorization": f"tma {make_test_init_data(user_id=123456789, username='admin')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Pub Hub", "category": "Бар", "city_id": "makhachkala"},
        headers=auth_owner
    )
    org_id = res_org.json()["id"]

    for uid in (2401, 2402):
        await client.post(
            f"/api/v1/organizations/{org_id}/subscribe",
            headers={"Authorization": f"tma {make_test_init_data(user_id=uid, username=f'sub_{uid}')}"}
        )

    ev_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Acoustic Evening",
            "description": "Live guitars",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": "2026-10-20T19:00:00Z",
            "venue_name": "Pub Hub Lounge",
            "organization_id": org_id
        },
        headers=auth_owner
    )
    event_id = ev_res.json()["id"]

    # Publish
    await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=auth_admin)

    # Dispatch using existing notification_service
    mock_client = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_client.post.return_value = mock_resp

    sent = await notify_organization_subscribers(event_id, http_client=mock_client, session=test_session)
    assert sent == 2
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_event_interest_cannot_use_custom_update_template(client, test_session):
    """Requirement D4.0.1: event_interest cannot target custom_update (general org news)."""
    owner_id = 3101
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_restrict')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Science Hub", "category": "Образование", "city_id": "makhachkala"},
        headers=auth_owner
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    ev_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Quantum Talk",
            "description": "Physics lecture",
            "category_id": "education",
            "city_id": "makhachkala",
            "start_at": "2026-11-01T18:00:00Z",
            "venue_name": "Main Hall",
            "organization_id": org_id
        },
        headers=auth_owner
    )
    assert ev_res.status_code == 201
    event_id = ev_res.json()["id"]

    # 1. Preview rejection
    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "event_interest",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "event_id": event_id,
            "custom_text": "Несвязанная новость"
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 400
    assert "шаблон 'custom_update' (новости организации) недопустим" in preview_res.json()["detail"]

    # 2. Create rejection
    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "event_interest",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "event_id": event_id,
            "custom_text": "Несвязанная новость"
        },
        headers=auth_owner
    )
    assert create_res.status_code == 400
    assert "шаблон 'custom_update' (новости организации) недопустим" in create_res.json()["detail"]


@pytest.mark.asyncio
async def test_delivered_marketing_messages_permanently_retained_in_db(client, test_session):
    """Requirement D4.0.1: Delivered messages are never deleted from DB after 24h limit passes."""
    owner_id = 3102
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_persist')}"}
    recipient_uid = 3103

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Book Club", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    # Recipient subscribes
    await client.post(
        f"/api/v1/organizations/{org_id}/subscribe",
        headers={"Authorization": f"tma {make_test_init_data(user_id=recipient_uid, username='reader')}"}
    )

    # Dispatch first broadcast
    mock_client = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_client.post.return_value = mock_resp

    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Первое сообщение"
        },
        headers=auth_owner
    )
    assert create_res.status_code == 200
    bcast_id = create_res.json()["id"]

    # Manually dispatch
    await dispatch_broadcast(broadcast_id=bcast_id, http_client=mock_client, session=test_session)

    # Verify recipient delivery record exists
    recip = (await test_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.broadcast_id == bcast_id)
    )).scalar_one()
    assert recip.status == RecipientStatus.SENT.value

    # Simulate 25 hours passing
    recip.sent_at = datetime.now(timezone.utc) - timedelta(hours=25)
    await test_session.commit()

    # Verify record still exists in DB permanently
    verified_recip = (await test_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.id == recip.id)
    )).scalar_one_or_none()
    assert verified_recip is not None
    assert verified_recip.status == RecipientStatus.SENT.value

    # Verify that now the user is eligible for a NEW broadcast because 24h limit expired,
    # but the old delivered broadcast record was NEVER purged or deleted
    preview_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Второе сообщение"
        },
        headers=auth_owner
    )
    assert preview_res.status_code == 200
    assert preview_res.json()["eligible_recipients"] == 1
    assert preview_res.json()["fatigued_recipients_count"] == 0

