import pytest
import time
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.services.broadcast_service import BroadcastRateLimiter, resume_active_broadcasts
from app.models.broadcast import Broadcast, BroadcastStatus, BroadcastRecipient, RecipientStatus
from app.models.organization import Organization
from app.models.user import User
from app.models.subscription import Subscription


def test_main_mini_app_direct_link_format():
    """
    Task 1: Ensures settings.get_event_deep_link returns the official
    Main Mini App Direct Link format: https://t.me/{bot_username}?startapp=event_{clean_id}
    without '/app' or '?start=' which cause Telegram to drop to bot chat.
    """
    event_id = "f3e3e034-7a1b-4c2d-9e5f-001122334455"
    deep_link = settings.get_event_deep_link(event_id)

    assert deep_link == f"https://t.me/{settings.clean_bot_username}?startapp=event_{event_id}"
    assert "/app?" not in deep_link
    assert "?start=" not in deep_link


def test_main_mini_app_direct_link_with_attribution():
    """
    Task 1: Ensures attribution tokens produce valid <=64 char startapp parameter.
    """
    event_id = "f3e3e034-7a1b-4c2d-9e5f-001122334455"
    token = "a1b2c3d4"
    deep_link = settings.get_event_deep_link(event_id, attribution_token=token)

    assert deep_link == f"https://t.me/{settings.clean_bot_username}?startapp=event_{event_id}_b_{token}"
    param = deep_link.split("startapp=")[1]
    assert len(param) <= 64


def test_main_mini_app_organization_direct_link():
    """
    Task 1: Ensures organization links follow Main Mini App Direct Link format.
    """
    org_id = "org_a1b2c3d4"
    org_link = settings.get_organization_deep_link(org_id)

    assert org_link == f"https://t.me/{settings.clean_bot_username}?startapp=org_a1b2c3d4"
    assert "/app?" not in org_link


def test_bot_start_event_replies_with_native_webapp_button():
    """
    Task 1: Fallback in Telegram bot chat for /start event_{id}.
    Must return an inline keyboard with a native 'web_app' button
    pointing to settings.WEBAPP_URL/?event_id={clean_event_id}.
    """
    from app.services.telegram_bot import handle_private_message
    message = {
        "chat": {"id": 123456789},
        "from": {"id": 123456789, "first_name": "TestUser"},
        "text": "/start event_f3e3e034-7a1b-4c2d-9e5f-001122334455"
    }

    response = handle_private_message(message)
    assert response is not None
    reply_markup = response.get("reply_markup", {})
    inline_keyboard = reply_markup.get("inline_keyboard", [])
    assert len(inline_keyboard) > 0

    # Find the event web_app button
    webapp_btn = None
    for row in inline_keyboard:
        for btn in row:
            if "web_app" in btn and "Открыть карточку события" in btn.get("text", ""):
                webapp_btn = btn
                break

    assert webapp_btn is not None
    assert "🎟 Открыть карточку события" in webapp_btn["text"]
    assert "event_id=f3e3e034-7a1b-4c2d-9e5f-001122334455" in webapp_btn["web_app"]["url"]
    assert webapp_btn["web_app"]["url"].startswith(f"{settings.WEBAPP_URL.rstrip('/')}/?")


@pytest.mark.asyncio
async def test_broadcast_rate_limiter_throttles_to_20_msg_per_sec():
    """
    Task 3: Verifies BroadcastRateLimiter smoothly throttles to 20 msg/sec.
    """
    limiter = BroadcastRateLimiter(rate=20.0)
    start_time = time.monotonic()

    # Acquire 10 permits: for rate=20, spacing is 0.05s, 10 permits should take ~0.45s
    for _ in range(10):
        await limiter.acquire()

    elapsed = time.monotonic() - start_time
    assert elapsed >= 0.40, f"Limiter was too fast: elapsed {elapsed}s for 10 permits"


@pytest.mark.asyncio
async def test_resume_active_broadcasts_on_startup(test_session: AsyncSession):
    """
    Task 3: Verifies resume_active_broadcasts detects interrupted broadcasts,
    resets stuck SENDING recipients to PENDING, and dispatches them in the background.
    """
    # 1. Create test users & org
    user1 = User(
        telegram_id=987654321,
        username="org_owner",
        first_name="Owner",
        created_at=datetime.now(timezone.utc)
    )
    user2 = User(
        telegram_id=987654322,
        username="org_member",
        first_name="Member",
        created_at=datetime.now(timezone.utc)
    )
    test_session.add_all([user1, user2])
    await test_session.flush()

    org = Organization(
        name="Test Org Resilient",
        slug="test-org-resilient",
        category="Концерты",
        owner_user_id=user1.id,
        created_at=datetime.now(timezone.utc)
    )
    test_session.add(org)
    await test_session.flush()

    # 2. Create interrupted broadcast with status 'processing'
    broadcast = Broadcast(
        organization_id=org.id,
        created_by_user_id=user1.id,
        target_type="organization_subscribers",
        custom_text="Interrupted broadcast message",
        status=BroadcastStatus.PROCESSING.value,
        total_recipients=2,
        sent_count=0,
        failed_count=0,
        created_at=datetime.now(timezone.utc)
    )
    test_session.add(broadcast)
    await test_session.flush()

    # Recipient 1: was stuck in SENDING
    r1 = BroadcastRecipient(
        broadcast_id=broadcast.id,
        user_id=user1.id,
        status=RecipientStatus.SENDING.value
    )
    # Recipient 2: already PENDING
    r2 = BroadcastRecipient(
        broadcast_id=broadcast.id,
        user_id=user2.id,
        status=RecipientStatus.PENDING.value
    )
    test_session.add_all([r1, r2])
    await test_session.commit()

    # 3. Call resume_active_broadcasts with mocked dispatch
    with patch("app.services.broadcast_service.dispatch_broadcast", new_callable=AsyncMock) as mock_dispatch:
        resumed_ids = await resume_active_broadcasts(test_session)
        assert len(resumed_ids) == 1
        assert resumed_ids[0] == broadcast.id

        # Allow background create_task to execute
        await asyncio.sleep(0.05)

        # Check that recipient 1 was reset from SENDING to PENDING
        reloaded_r1 = await test_session.get(BroadcastRecipient, r1.id)
        assert reloaded_r1.status == RecipientStatus.PENDING.value

        # Check dispatch_broadcast was called for the broadcast
        assert mock_dispatch.called
        assert mock_dispatch.call_args[0][1] == broadcast.id


@pytest.mark.asyncio
async def test_notifications_permission_endpoint(client, test_session: AsyncSession):
    """
    Task 2: Tests POST /api/v1/users/me/notifications-permission.
    When allowed=True is passed, user's subscriptions get notifications_enabled=True.
    """
    from app.main import app
    from app.api.deps import get_current_user

    # 1. Create user and subscription with notifications_enabled=False
    user = User(
        telegram_id=11223344,
        username="subscriber_1",
        first_name="Sub",
        created_at=datetime.now(timezone.utc)
    )
    test_session.add(user)
    await test_session.flush()

    org = Organization(
        name="Org To Subscribe",
        slug="org-to-subscribe",
        category="Культура",
        owner_user_id=user.id,
        created_at=datetime.now(timezone.utc)
    )
    test_session.add(org)
    await test_session.flush()

    sub = Subscription(
        user_id=user.id,
        organization_id=org.id,
        notifications_enabled=False,
        created_at=datetime.now(timezone.utc)
    )
    test_session.add(sub)
    await test_session.commit()

    # 2. Call endpoint with mocked auth
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = await client.post(
            "/api/v1/users/me/notifications-permission",
            json={"allowed": True}
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "allowed": True}

        # 3. Verify subscription was updated in DB
        reloaded_sub = await test_session.get(Subscription, sub.id)
        assert reloaded_sub.notifications_enabled is True
    finally:
        app.dependency_overrides.clear()
