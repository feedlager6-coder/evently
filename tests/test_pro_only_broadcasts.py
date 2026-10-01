import pytest
import httpx
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.event import Event, EventStatus
from app.models.organization import Organization
from app.models.organization_plan import PlanType
from app.models.broadcast import BroadcastType
from app.services.entitlement_service import EntitlementService
from app.services.notification_service import (
    resolve_event_cover_url,
    send_telegram_event_message,
    notify_event_updated,
    notify_event_cancelled,
)


@pytest.mark.asyncio
async def test_01_free_org_cannot_create_broadcast(client, test_session):
    """1. Free organization cannot create broadcast: returns HTTP 403 ENTITLEMENT_REQUIRED."""
    owner_id = 9501
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_free_bcast')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Free Org One", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth,
    )
    assert res_org.status_code in (200, 201)
    org_id = res_org.json()["id"]

    # Subscriber
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9601, username='sub_free_1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    # Attempt to create broadcast
    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Marketing text from Free org",
        },
        headers=auth,
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["code"] == "ENTITLEMENT_REQUIRED"
    assert detail["capability"] == "broadcasts_extended"
    assert detail["required_plan"] == "pro"


@pytest.mark.asyncio
async def test_02_free_org_preview_returns_status(client, test_session):
    """2. Free organization broadcast preview reflects audience calculation."""
    owner_id = 9502
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_free_prev')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Free Preview Org", "category": "Клуб", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_prev = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Preview calculation",
        },
        headers=auth,
    )
    assert res_prev.status_code == 200
    assert "eligible_recipients" in res_prev.json()


@pytest.mark.asyncio
async def test_03_pro_org_can_create_broadcast(client, test_session):
    """3. Pro organization can create broadcast within limit."""
    owner_id = 9503
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_pro_success')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Pro Active Hall", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Upgrade to Pro
    await EntitlementService.set_organization_plan(test_session, org_id, plan="pro")

    # Subscribe
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9602, username='sub_pro_success')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    # Broadcast
    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Pro marketing message",
        },
        headers=auth,
    )
    assert res.status_code == 200
    assert res.json()["delivered_count"] == 1


@pytest.mark.asyncio
async def test_04_05_manual_transactional_creation_blocked(client, test_session):
    """4 & 5. Manual transactional creation via API is blocked with HTTP 400 Bad Request."""
    owner_id = 9504
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_trans_block')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Anti Abuse Org", "category": "Театр", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Try preview with transactional
    prev_res = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "transactional",
            "template_key": "event_update",
            "custom_text": "Sneaky update",
        },
        headers=auth,
    )
    assert prev_res.status_code == 400
    assert "отправляются системой автоматически" in prev_res.json()["detail"]

    # Try create with transactional
    create_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "transactional",
            "template_key": "event_update",
            "custom_text": "Sneaky manual transactional",
        },
        headers=auth,
    )
    assert create_res.status_code == 400
    assert "отправляются системой автоматически" in create_res.json()["detail"]


@pytest.mark.asyncio
async def test_06_event_time_change_triggers_notification(client, test_session):
    """6. Changing event start time triggers automatic transactional notification."""
    owner_id = 9505
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_time_change')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Time Change Org", "category": "Лекторий", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Открытая лекция",
            "description": "Описание лекции для студентов",
            "category_id": "education",
            "start_at": "2026-11-10T18:00:00Z",
            "venue_name": "Конференц-зал",
            "address": "ул. Ленина 1",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    event_id = res_ev.json()["id"]

    # Publish event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Add subscriber
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9603, username='sub_lecture')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    # Patch start_at with mock on notify_event_updated
    with patch("app.services.notification_service.notify_event_updated", new_callable=AsyncMock) as mock_notify:
        mock_notify.return_value = 1

        patch_res = await client.patch(
            f"/api/v1/events/{event_id}",
            json={"start_at": "2026-11-10T19:30:00Z"},
            headers=auth,
        )
        assert patch_res.status_code == 200
        assert mock_notify.called
        changes = mock_notify.call_args.args[1]
        assert changes["time_changed"] is True


@pytest.mark.asyncio
async def test_07_event_venue_change_triggers_notification(client, test_session):
    """7. Changing venue/address triggers automatic transactional notification."""
    owner_id = 9506
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_venue_change')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Venue Change Org", "category": "Спорт", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Турнир по шахматам",
            "description": "Описание шахматного турнира",
            "category_id": "sports",
            "start_at": "2026-11-12T12:00:00Z",
            "venue_name": "Старый зал",
            "address": "ул. Старая 5",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    event_id = res_ev.json()["id"]

    # Publish event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Add subscriber
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9604, username='sub_chess')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    with patch("app.services.notification_service.notify_event_updated", new_callable=AsyncMock) as mock_notify:
        mock_notify.return_value = 1

        patch_res = await client.patch(
            f"/api/v1/events/{event_id}",
            json={"venue_name": "Новая Арена", "address": "пр. Новый 10"},
            headers=auth,
        )
        assert patch_res.status_code == 200
        assert mock_notify.called
        changes = mock_notify.call_args.args[1]
        assert changes["venue_changed"] is True


@pytest.mark.asyncio
async def test_08_event_cancellation_triggers_notification(client, test_session):
    """8. Cancelling an event triggers automatic transactional notification."""
    owner_id = 9507
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_cancel')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Cancel Org", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Отменяемый Концерт",
            "description": "Описание музыкального концерта",
            "category_id": "concerts",
            "start_at": "2026-11-15T20:00:00Z",
            "venue_name": "Концертный зал",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9605, username='sub_cancel_event')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    with patch("app.services.notification_service.notify_event_cancelled", new_callable=AsyncMock) as mock_cancel:
        mock_cancel.return_value = 1

        del_res = await client.delete(f"/api/v1/events/{event_id}", headers=auth)
        assert del_res.status_code == 200
        assert mock_cancel.called


@pytest.mark.asyncio
async def test_09_10_transactional_exempt_from_quota_and_no_attribution(client, test_session):
    """9 & 10. System notifications do NOT consume quota and have NO marketing attribution tokens."""
    owner_id = 9508
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_quota_check')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Quota Check Org", "category": "Спорт", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Спортивный турнир",
            "description": "Описание спортивного турнира",
            "category_id": "sports",
            "start_at": "2026-11-18T19:00:00Z",
            "venue_name": "Спорткомплекс",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Initial marketing usage
    usage_before = await EntitlementService.get_monthly_broadcast_usage(test_session, org_id)
    assert usage_before == 0

    # Trigger update
    with patch("app.services.notification_service.notify_event_updated", new_callable=AsyncMock) as mock_notify:
        mock_notify.return_value = 1
        await client.patch(
            f"/api/v1/events/{event_id}",
            json={"start_at": "2026-11-18T20:00:00Z"},
            headers=auth,
        )
        assert mock_notify.called

    # Check marketing usage remains 0
    usage_after = await EntitlementService.get_monthly_broadcast_usage(test_session, org_id)
    assert usage_after == 0


@pytest.mark.asyncio
async def test_11_insignificant_changes_do_not_trigger_notification(client, test_session):
    """11. Event update without significant changes (e.g. description only) does NOT trigger notification."""
    owner_id = 9509
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_desc_edit')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Desc Edit Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Художественная выставка",
            "description": "Первоначальное описание выставки картин",
            "category_id": "exhibitions",
            "start_at": "2026-11-25T14:00:00Z",
            "venue_name": "Галерея",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    with patch("app.services.notification_service.notify_event_updated", new_callable=AsyncMock) as mock_notify:
        # Patch only description
        patch_res = await client.patch(
            f"/api/v1/events/{event_id}",
            json={"description": "Обновленное подробное описание выставки картин"},
            headers=auth,
        )
        assert patch_res.status_code == 200
        # Must NOT dispatch notifications
        assert not mock_notify.called


@pytest.mark.asyncio
async def test_12_13_send_photo_with_fallback():
    """12 & 13. sendPhoto used when cover image is present, with fallback to sendMessage."""
    async with httpx.AsyncClient() as client:
        # Case A: valid image URL, sendPhoto succeeds
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, json=lambda: {"ok": True})
            success = await send_telegram_event_message(
                client=client,
                bot_token="fake_bot_token",
                chat_id=12345,
                text="<b>Title</b>\nDetails",
                reply_markup={"inline_keyboard": []},
                image_url="https://images.unsplash.com/photo-test",
            )
            assert success is True
            assert "sendPhoto" in mock_post.call_args_list[0].args[0]

        # Case B: sendPhoto fails (400 bad image), falls back to sendMessage
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                AsyncMock(status_code=400, text="Wrong file identifier"),
                AsyncMock(status_code=200, json=lambda: {"ok": True}),
            ]
            success = await send_telegram_event_message(
                client=client,
                bot_token="fake_bot_token",
                chat_id=12345,
                text="<b>Title</b>\nDetails",
                reply_markup={"inline_keyboard": []},
                image_url="https://broken-image.com/img.jpg",
            )
            assert success is True
            assert "sendPhoto" in mock_post.call_args_list[0].args[0]
            assert "sendMessage" in mock_post.call_args_list[1].args[0]

        # Case C: no cover image, goes directly to sendMessage
        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, json=lambda: {"ok": True})
            success = await send_telegram_event_message(
                client=client,
                bot_token="fake_bot_token",
                chat_id=12345,
                text="<b>Title</b>\nDetails",
                reply_markup={"inline_keyboard": []},
                image_url=None,
            )
            assert success is True
            assert len(mock_post.call_args_list) == 1
            assert "sendMessage" in mock_post.call_args_list[0].args[0]


def test_14_relative_image_url_resolution(monkeypatch):
    """14. Relative image URLs are resolved to absolute URLs."""
    monkeypatch.setattr(settings, "PUBLIC_HOST", "https://ivently.app")

    assert resolve_event_cover_url(None) is None
    assert resolve_event_cover_url("") is None
    assert resolve_event_cover_url("https://example.com/pic.jpg") == "https://example.com/pic.jpg"
    assert resolve_event_cover_url("/api/v1/uploads/img.png") == "https://ivently.app/api/v1/uploads/img.png"
    assert resolve_event_cover_url("uploads/img.png") == "https://ivently.app/uploads/img.png"


@pytest.mark.asyncio
async def test_15_existing_event_creation_moderation_unbroken(client, test_session):
    """15. Existing event creation and moderation flow remains unbroken."""
    owner_id = 9515
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_unbroken')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Unbroken Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Событие для проверки модерации",
            "description": "Описание события для проверки статуса",
            "category_id": "concerts",
            "start_at": "2026-12-01T15:00:00Z",
            "venue_name": "Театр поэзии",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    assert res_ev.status_code == 201
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    assert ev_db.status == EventStatus.PENDING.value


@pytest.mark.asyncio
async def test_16_existing_subscriber_audience_unbroken(client, test_session):
    """16. Existing subscriber and audience flow remains unbroken."""
    owner_id = 9516
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_sub_flow')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Audience Flow Org", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    user_id = 9616
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='sub_user_unbroken')}"}
    sub_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)
    assert sub_res.status_code == 200
    assert sub_res.json()["is_subscribed"] is True

    # Audience list for organizer
    aud_res = await client.get(f"/api/v1/organizer/audience?org_id={org_id}", headers=auth)
    assert aud_res.status_code == 200
    assert aud_res.json()["total_subscribers"] == 1


@pytest.mark.asyncio
async def test_17_existing_attendance_interest_unbroken(client, test_session):
    """17. Existing attendance/interest flow remains unbroken."""
    owner_id = 9517
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_interest_flow')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Interest Flow Org", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Встреча клуба",
            "description": "Описание встречи в уютном коворкинге",
            "category_id": "business",
            "start_at": "2026-12-05T18:00:00Z",
            "venue_name": "Коворкинг",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    assert res_ev.status_code == 201
    event_id = res_ev.json()["id"]

    user_id = 9617
    user_auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='fan_user')}"}

    # Mark interest
    interest_res = await client.post(f"/api/v1/events/{event_id}/interest", headers=user_auth)
    assert interest_res.status_code == 200
    assert interest_res.json()["is_interested"] is True


@pytest.mark.asyncio
async def test_18_multi_org_isolation_pro_vs_free(client, test_session):
    """18. Multi-org isolation: Pro entitlement on Org A does NOT allow broadcasts from Org B (Free)."""
    owner_id = 9518
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_multi_two')}"}

    res_a = await client.post(
        "/api/v1/organizations",
        json={"name": "Org A Pro", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_a_id = res_a.json()["id"]

    res_b = await client.post(
        "/api/v1/organizations",
        json={"name": "Org B Free", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth,
    )
    org_b_id = res_b.json()["id"]

    # Upgrade ONLY Org A to Pro
    await EntitlementService.set_organization_plan(test_session, org_a_id, plan="pro")

    # Add subscriber to both
    sub_auth_a = {"Authorization": f"tma {make_test_init_data(user_id=9618, username='sub_multi_a')}"}
    await client.post(f"/api/v1/organizations/{org_a_id}/subscribe", headers=sub_auth_a)

    sub_auth_b = {"Authorization": f"tma {make_test_init_data(user_id=9619, username='sub_multi_b')}"}
    await client.post(f"/api/v1/organizations/{org_b_id}/subscribe", headers=sub_auth_b)

    # Broadcast from Org A (Pro) -> SUCCESS
    res_bcast_a = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_a_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Org A Pro announcement",
        },
        headers=auth,
    )
    assert res_bcast_a.status_code == 200

    # Broadcast from Org B (Free) -> MUST BE BLOCKED (403 ENTITLEMENT_REQUIRED)
    res_bcast_b = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_b_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Org B Free illegal announcement",
        },
        headers=auth,
    )
    assert res_bcast_b.status_code == 403
    assert res_bcast_b.json()["detail"]["code"] == "ENTITLEMENT_REQUIRED"
    assert res_bcast_b.json()["detail"]["required_plan"] == "pro"
