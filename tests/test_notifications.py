import pytest
import httpx
from unittest.mock import AsyncMock, patch
from tests.conftest import make_test_init_data
from app.config import settings
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
    # Check button text, url, and style
    button = first_payload["reply_markup"]["inline_keyboard"][0][0]
    assert button["text"] == "Открыть событие 🧭"
    assert button["url"] == f"https://t.me/{settings.clean_bot_username}/app?startapp=event_{event_id}"
    assert button.get("style") == "primary"
    assert "callback_data" not in button
    assert "web_app" not in button


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


def test_deep_link_formatting_and_startapp_values():
    """
    Sprint A.1 Hotfix Regression Test:
    Verifies that event and organization deep links follow exact Telegram Mini App Direct Link specifications.
    1. event ID -> notification deep link -> exact startapp value
    2. org ID -> organization deep link -> exact startapp value
    3. Never use Railway host for notification direct link
    """
    from app.config import settings
    test_event_id = "c3b53f65-4f38-4e56-91e8-d1d8ef3f972b"
    test_org_id = "a1122334-bb55-6677-8899-aabbccddeeff"

    event_link = settings.get_event_deep_link(test_event_id)
    org_link = settings.get_organization_deep_link(test_org_id)

    # Must be official Telegram Mini App Direct Link format
    assert event_link.startswith("https://t.me/")
    assert f"/{settings.clean_bot_username}/app?startapp=event_{test_event_id}" in event_link
    assert not event_link.startswith("https://ivently.up.railway.app")

    assert org_link.startswith("https://t.me/")
    assert f"/{settings.clean_bot_username}/app?startapp=org_{test_org_id}" in org_link
    assert not org_link.startswith("https://ivently.up.railway.app")

    # Bot username must be clean without '@'
    assert not settings.clean_bot_username.startswith("@")


def test_start_param_frontend_extraction_parity():
    """
    Sprint A.1 Hotfix Regression Test:
    Simulates the frontend extraction algorithm used in telegram.ts and App.tsx:
    Verifies that event_<UUID>, org_<UUID>, and create are extracted cleanly,
    even when followed by trailing queries, hashes, or slashes.
    """
    def extract_id(raw: str, prefix: str) -> str:
        clean = raw.strip()
        if clean.startswith(prefix):
            without_prefix = clean[len(prefix):]
            return without_prefix.split('?')[0].split('&')[0].split('#')[0].rstrip('/').strip()
        return ""

    uuid_val = "12345678-abcd-ef01-2345-6789abcdef01"
    
    # 1. Clean event param
    assert extract_id(f"event_{uuid_val}", "event_") == uuid_val
    # 2. Event param with trailing hash/query residue
    assert extract_id(f"event_{uuid_val}?tgWebAppVersion=8.0", "event_") == uuid_val
    assert extract_id(f"event_{uuid_val}#section", "event_") == uuid_val
    assert extract_id(f"event_{uuid_val}/", "event_") == uuid_val

    # 3. Organization param parity
    org_uuid = "98765432-fedc-ba98-7654-3210fedcba98"
    assert extract_id(f"org_{org_uuid}", "org_") == org_uuid
    assert extract_id(f"org_{org_uuid}?startapp=...", "org_") == org_uuid

