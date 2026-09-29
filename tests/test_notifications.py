import pytest
import httpx
from unittest.mock import AsyncMock, patch
from tests.conftest import make_test_init_data
from app.services.notification_service import notify_organization_subscribers


@pytest.mark.asyncio
async def test_notification_service_dispatches_messages(client, test_session):
    """
    Directly tests notify_organization_subscribers:
    Verifies message text formatting, startapp deep link, chat_ids, and resilience.
    """
    owner_init = make_test_init_data(user_id=2001, username="notif_owner")
    headers_owner = {"Authorization": f"tma {owner_init}"}
    admin_init = make_test_init_data(user_id=123456789, username="admin")
    headers_admin = {"Authorization": f"tma {admin_init}"}

    # Subscribed users
    sub1_init = make_test_init_data(user_id=3001, username="sub1")
    sub2_init = make_test_init_data(user_id=3002, username="sub2")

    # 1. Create org
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Coffee Lab", "category": "Кафе", "city_id": "makhachkala"},
        headers=headers_owner
    )
    org_id = org_res.json()["id"]

    # 2. Both users subscribe
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers={"Authorization": f"tma {sub1_init}"})
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers={"Authorization": f"tma {sub2_init}"})

    # 3. Create event under org
    ev_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Acoustic Live Music",
            "description": "Live jazz and coffee evening.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": "2026-10-04T20:00:00Z",
            "venue_name": "Coffee Lab Main Room",
            "address": "пр. Ленина, 10",
            "organization_id": org_id
        },
        headers=headers_owner
    )
    event_id = ev_res.json()["id"]

    # 4. While pending, notification must NOT be sent
    sent_pending = await notify_organization_subscribers(event_id, session=test_session)
    assert sent_pending == 0

    # 5. Publish event via admin
    await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=headers_admin)

    # 6. Test with a mock HTTP client
    mock_http_client = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_http_client.post.return_value = mock_resp

    sent_published = await notify_organization_subscribers(event_id, http_client=mock_http_client, session=test_session)
    assert sent_published == 2
    assert mock_http_client.post.call_count == 2

    # Verify call parameters
    calls = mock_http_client.post.call_args_list
    target_chat_ids = {call.kwargs["json"]["chat_id"] for call in calls}
    assert 3001 in target_chat_ids
    assert 3002 in target_chat_ids

    first_payload = calls[0].kwargs["json"]
    assert "Coffee Lab" in first_payload["text"]
    assert "Acoustic Live Music" in first_payload["text"]
    # Check startapp deep link
    button_url = first_payload["reply_markup"]["inline_keyboard"][0][0]["url"]
    assert f"startapp=event_{event_id}" in button_url


@pytest.mark.asyncio
async def test_notification_telegram_error_resilience(client, test_session):
    """Verifies that an error for one subscriber does not disrupt notifications for others."""
    owner_init = make_test_init_data(user_id=2002, username="owner_resilient")
    headers_owner = {"Authorization": f"tma {owner_init}"}
    admin_init = make_test_init_data(user_id=123456789, username="admin")
    headers_admin = {"Authorization": f"tma {admin_init}"}

    sub1_init = make_test_init_data(user_id=4001, username="sub_fail")
    sub2_init = make_test_init_data(user_id=4002, username="sub_success")

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Cinema 05", "category": "Культура"},
        headers=headers_owner
    )
    org_id = org_res.json()["id"]

    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers={"Authorization": f"tma {sub1_init}"})
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers={"Authorization": f"tma {sub2_init}"})

    ev_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Movie Night",
            "description": "Classic movie screening.",
            "category_id": "parties",
            "city_id": "makhachkala",
            "start_at": "2026-10-05T20:00:00Z",
            "venue_name": "Cinema Hall",
            "address": "ул. Коркмасова, 1",
            "organization_id": org_id
        },
        headers=headers_owner
    )
    event_id = ev_res.json()["id"]
    await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=headers_admin)

    # First user call raises exception (e.g. timeout), second succeeds
    mock_http_client = AsyncMock()
    mock_resp_success = AsyncMock()
    mock_resp_success.status_code = 200

    mock_http_client.post.side_effect = [
        httpx.ConnectTimeout("Telegram API timeout"),
        mock_resp_success
    ]

    sent_count = await notify_organization_subscribers(event_id, http_client=mock_http_client, session=test_session)
    assert sent_count == 1
    assert mock_http_client.post.call_count == 2
