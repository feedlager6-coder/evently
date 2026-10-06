import pytest
import httpx
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.models.user import User
from app.models.organization import Organization
from app.models.event import Event, EventStatus
from app.models.interest import EventInterest
from app.models.subscription import Subscription
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
    dispatch_broadcast,
)


@pytest.fixture(autouse=True)
def setup_entitlements(monkeypatch):
    """Bypasses entitlement quota checks for testing broadcast status truth."""
    from app.services.entitlement_service import EntitlementService
    async def mock_require(session, org_id, capability):
        return True
    async def mock_enforce(session, org_id, broadcast_type="marketing"):
        return True
    monkeypatch.setattr(EntitlementService, "require_entitlement", mock_require)
    monkeypatch.setattr(EntitlementService, "enforce_broadcast_capacity", mock_enforce)


@pytest.mark.asyncio
async def test_event_interest_audience_accuracy_and_isolation(client, test_session):
    """
    Verifies that EventInterest audience selects exactly and only the users
    who tapped 'Хочу пойти' on that specific event, with strict organization isolation.
    """
    owner_id = 7001
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_org')}"}

    # 1. Create Organization 1 and Event 1
    org1_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Org Alpha", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth_owner
    )
    assert org1_res.status_code == 201
    org1_id = org1_res.json()["id"]

    ev1_res = await client.post(
        "/api/v1/events",
        json={
            "organization_id": org1_id,
            "title": "Alpha Live Concert",
            "description": "Live musical concert event description in Alpha Hall.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "venue_name": "Alpha Hall",
            "address": "Lenina 1",
            "start_at": "2026-12-01T19:00:00Z",
            "price_amount": 500,
            "price_currency": "RUB"
        },
        headers=auth_owner
    )
    assert ev1_res.status_code == 201
    ev1_id = ev1_res.json()["id"]

    # 2. Create Organization 2 and Event 2
    org2_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Org Beta", "category": "Вечеринки", "city_id": "makhachkala"},
        headers=auth_owner
    )
    assert org2_res.status_code == 201
    org2_id = org2_res.json()["id"]

    ev2_res = await client.post(
        "/api/v1/events",
        json={
            "organization_id": org2_id,
            "title": "Beta Party Night",
            "description": "Live evening party event description on Beta Stage.",
            "category_id": "parties",
            "city_id": "makhachkala",
            "venue_name": "Beta Club",
            "address": "Lenina 2",
            "start_at": "2026-12-02T19:00:00Z",
            "price_amount": 700,
            "price_currency": "RUB"
        },
        headers=auth_owner
    )
    assert ev2_res.status_code == 201
    ev2_id = ev2_res.json()["id"]

    # 3. User 7010 and 7011 express interest in Event 1
    auth_u1 = {"Authorization": f"tma {make_test_init_data(user_id=7010, username='user_7010')}"}
    auth_u2 = {"Authorization": f"tma {make_test_init_data(user_id=7011, username='user_7011')}"}
    r1 = await client.post(f"/api/v1/events/{ev1_id}/interest", headers=auth_u1)
    assert r1.status_code == 200
    r2 = await client.post(f"/api/v1/events/{ev1_id}/interest", headers=auth_u2)
    assert r2.status_code == 200

    # 4. User 7012 expresses interest in Event 2 (different org!)
    auth_u3 = {"Authorization": f"tma {make_test_init_data(user_id=7012, username='user_7012')}"}
    r3 = await client.post(f"/api/v1/events/{ev2_id}/interest", headers=auth_u3)
    assert r3.status_code == 200

    owner_user = (await test_session.execute(select(User).where(User.telegram_id == owner_id))).scalar_one()

    # 5. Calculate audience for Org 1 + Event 1
    aud = await calculate_audience(
        session=test_session,
        organizer_user_id=owner_user.id,
        organization_id=org1_id,
        target_type=BroadcastTargetType.EVENT_INTEREST.value,
        broadcast_type=BroadcastType.MARKETING.value,
        event_id=ev1_id
    )

    assert aud["total_audience"] == 2
    assert len(aud["eligible_user_ids"]) == 2

    # Query internal user IDs for 7010 and 7011
    u10 = (await test_session.execute(select(User).where(User.telegram_id == 7010))).scalar_one()
    u11 = (await test_session.execute(select(User).where(User.telegram_id == 7011))).scalar_one()
    u12 = (await test_session.execute(select(User).where(User.telegram_id == 7012))).scalar_one()

    assert u10.id in aud["eligible_user_ids"]
    assert u11.id in aud["eligible_user_ids"]
    assert u12.id not in aud["eligible_user_ids"]  # Org 2 participant isolated!


@pytest.mark.asyncio
async def test_broadcast_truth_telegram_success_marks_completed(test_session):
    """
    When Telegram API returns 200 OK with message_id:
    Recipient is marked SENT, telegram_message_id is stored, broadcast status is COMPLETED.
    """
    user = User(telegram_id=8801, username="test_rec_success", first_name="RecSuccess")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    org = Organization(
        id="org-test-truth-1",
        slug="truth-org-1",
        name="Truth Org",
        category="Music",
        owner_user_id=user.id
    )
    test_session.add(org)
    await test_session.commit()

    bcast = Broadcast(
        organization_id=org.id,
        created_by_user_id=user.id,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.CUSTOM_UPDATE.value,
        status=BroadcastStatus.QUEUED.value,
        custom_text="Hello truth world!",
        total_recipients=1,
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    rec = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=user.id,
        status=RecipientStatus.PENDING.value
    )
    test_session.add(rec)
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"ok": true, "result": {"message_id": 118}}'
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 118}}
    mock_client.post.return_value = mock_resp

    result = await dispatch_broadcast(
        session=test_session,
        broadcast_id=bcast.id,
        http_client=mock_client
    )

    assert result.status == BroadcastStatus.COMPLETED.value
    assert result.sent_count == 1
    assert result.failed_count == 0
    assert result.blocked_count == 0

    await test_session.refresh(rec)
    assert rec.status == RecipientStatus.SENT.value
    assert rec.telegram_message_id == 118


@pytest.mark.asyncio
async def test_broadcast_truth_cant_initiate_marks_failed(test_session):
    """
    When Telegram API returns 403 Forbidden 'bot can't initiate conversation with a user':
    Recipient is marked FAILED (code cant_initiate_conversation).
    Broadcast status MUST be FAILED (NOT COMPLETED!). sent_count must be 0.
    """
    user = User(telegram_id=8802, username="test_rec_cant_init", first_name="RecCantInit")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    org = Organization(
        id="org-test-truth-2",
        slug="truth-org-2",
        name="Truth Org 2",
        category="Music",
        owner_user_id=user.id
    )
    test_session.add(org)
    await test_session.commit()

    bcast = Broadcast(
        organization_id=org.id,
        created_by_user_id=user.id,
        target_type=BroadcastTargetType.EVENT_INTEREST.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.CUSTOM_UPDATE.value,
        status=BroadcastStatus.QUEUED.value,
        custom_text="Hello can't initiate test!",
        total_recipients=1,
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    rec = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=user.id,
        status=RecipientStatus.PENDING.value
    )
    test_session.add(rec)
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = '{"ok": false, "error_code": 403, "description": "Forbidden: bot can\'t initiate conversation with a user"}'
    mock_resp.json.return_value = {"ok": False, "error_code": 403, "description": "Forbidden: bot can't initiate conversation with a user"}
    mock_client.post.return_value = mock_resp

    result = await dispatch_broadcast(
        session=test_session,
        broadcast_id=bcast.id,
        http_client=mock_client
    )

    assert result.status == BroadcastStatus.FAILED.value
    assert result.sent_count == 0
    assert result.failed_count == 1
    assert result.blocked_count == 0

    await test_session.refresh(rec)
    assert rec.status == RecipientStatus.FAILED.value
    assert rec.error_code == "cant_initiate_conversation"
    assert "не начал диалог" in rec.error_message


@pytest.mark.asyncio
async def test_broadcast_truth_bot_blocked_marks_blocked(test_session):
    """
    When Telegram API returns 403 Forbidden 'bot was blocked by the user':
    Recipient is marked BLOCKED (code bot_blocked).
    Broadcast blocked_count is 1, status is FAILED.
    User's organization subscription notifications are disabled.
    """
    user = User(telegram_id=8803, username="test_rec_blocked", first_name="RecBlocked")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    org = Organization(
        id="org-test-truth-3",
        slug="truth-org-3",
        name="Truth Org 3",
        category="Music",
        owner_user_id=user.id
    )
    test_session.add(org)
    await test_session.commit()

    sub = Subscription(user_id=user.id, organization_id=org.id, notifications_enabled=True)
    test_session.add(sub)
    await test_session.commit()

    bcast = Broadcast(
        organization_id=org.id,
        created_by_user_id=user.id,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.CUSTOM_UPDATE.value,
        status=BroadcastStatus.QUEUED.value,
        custom_text="Hello blocked test!",
        total_recipients=1,
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    rec = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=user.id,
        status=RecipientStatus.PENDING.value
    )
    test_session.add(rec)
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = '{"ok": false, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}'
    mock_resp.json.return_value = {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}
    mock_client.post.return_value = mock_resp

    result = await dispatch_broadcast(
        session=test_session,
        broadcast_id=bcast.id,
        http_client=mock_client
    )

    assert result.status == BroadcastStatus.FAILED.value
    assert result.sent_count == 0
    assert result.blocked_count == 1

    await test_session.refresh(rec)
    assert rec.status == RecipientStatus.BLOCKED.value
    assert rec.error_code in ("403", "bot_blocked")

    await test_session.refresh(sub)
    assert sub.notifications_enabled is False


@pytest.mark.asyncio
async def test_broadcast_truth_network_timeout_marks_failed(test_session):
    """
    When Telegram API connection times out:
    Recipient is marked FAILED (code network_timeout).
    Broadcast status is FAILED.
    """
    user = User(telegram_id=8804, username="test_rec_timeout", first_name="RecTimeout")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    org = Organization(
        id="org-test-truth-4",
        slug="truth-org-4",
        name="Truth Org 4",
        category="Music",
        owner_user_id=user.id
    )
    test_session.add(org)
    await test_session.commit()

    bcast = Broadcast(
        organization_id=org.id,
        created_by_user_id=user.id,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.CUSTOM_UPDATE.value,
        status=BroadcastStatus.QUEUED.value,
        custom_text="Hello timeout test!",
        total_recipients=1,
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    rec = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=user.id,
        status=RecipientStatus.PENDING.value
    )
    test_session.add(rec)
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out after 8.0s")

    result = await dispatch_broadcast(
        session=test_session,
        broadcast_id=bcast.id,
        http_client=mock_client
    )

    assert result.status == BroadcastStatus.FAILED.value
    assert result.sent_count == 0
    assert result.failed_count == 1

    await test_session.refresh(rec)
    assert rec.status == RecipientStatus.FAILED.value
    assert rec.error_code == "network_timeout"


@pytest.mark.asyncio
async def test_broadcast_truth_ok_false_with_200_marks_failed(test_session):
    """
    When Telegram API returns HTTP 200 but body contains ok=false:
    Recipient MUST NOT be marked SENT! Recipient is marked FAILED.
    """
    user = User(telegram_id=8805, username="test_rec_okfalse", first_name="RecOkFalse")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    org = Organization(
        id="org-test-truth-5",
        slug="truth-org-5",
        name="Truth Org 5",
        category="Music",
        owner_user_id=user.id
    )
    test_session.add(org)
    await test_session.commit()

    bcast = Broadcast(
        organization_id=org.id,
        created_by_user_id=user.id,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.CUSTOM_UPDATE.value,
        status=BroadcastStatus.QUEUED.value,
        custom_text="Hello ok=false test!",
        total_recipients=1,
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    rec = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=user.id,
        status=RecipientStatus.PENDING.value
    )
    test_session.add(rec)
    await test_session.commit()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"ok": false, "error_code": 400, "description": "Bad Request: message is too long"}'
    mock_resp.json.return_value = {"ok": False, "error_code": 400, "description": "Bad Request: message is too long"}
    mock_client.post.return_value = mock_resp

    result = await dispatch_broadcast(
        session=test_session,
        broadcast_id=bcast.id,
        http_client=mock_client
    )

    assert result.status == BroadcastStatus.FAILED.value
    assert result.sent_count == 0
    assert result.failed_count == 1

    await test_session.refresh(rec)
    assert rec.status == RecipientStatus.FAILED.value
    assert rec.error_code == "400"


@pytest.mark.asyncio
async def test_cities_endpoint_search_and_cache_control(client):
    """
    Verifies that:
    1. /api/v1/cities without search sets Cache-Control header.
    2. /api/v1/cities?q=makhachkala performs search and limits results.
    """
    res = await client.get("/api/v1/cities")
    assert res.status_code == 200
    assert "public, max-age=86400" in res.headers.get("Cache-Control", "")
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0

    res_search = await client.get("/api/v1/cities?q=makhachkala")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert len(search_data) >= 1
    assert any(c["id"] == "makhachkala" for c in search_data)


@pytest.mark.asyncio
async def test_telegram_webhook_write_access_allowed(client):
    """
    Verifies that Telegram webhook handles write_access_allowed update
    and responds with confirmation message and Mini App button.
    """
    update = {
        "update_id": 99901,
        "message": {
            "message_id": 12,
            "from": {"id": 8653761136, "is_bot": False, "first_name": "TestUser"},
            "chat": {"id": 8653761136, "type": "private"},
            "date": 1728250000,
            "write_access_allowed": {
                "from_request": True
            }
        }
    }
    res = await client.post("/api/v1/telegram/webhook", json=update)
    assert res.status_code == 200
    data = res.json()
    assert data.get("method") == "sendMessage" or data.get("ok") is True
