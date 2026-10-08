import logging
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import select

from tests.conftest import make_test_init_data, TEST_BOT_TOKEN
from app.config import settings
from app.models.event import Event, EventStatus
from app.models.city import City
from app.models.category import Category
from app.models.user import User
from app.services.telegram_bot import (
    save_prepared_inline_share_message,
    check_public_image_validity,
    handle_inline_query,
    build_event_inline_result
)
from app.services.event_service import get_event_details


@pytest.fixture
def auth_headers():
    user_id = 99887766
    init_data = make_test_init_data(user_id=user_id, username="share_test_user")
    return {"Authorization": f"tma {init_data}"}


@pytest.mark.asyncio
async def test_01_prepare_share_published_event_200(client, test_session, auth_headers):
    """1. Published event returns 200 OK with prepared_message_id and expiration_date."""
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    event = Event(
        title="Valid Share Event",
        description="Event for share test",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) + timedelta(days=5),
        venue_name="Concert Hall",
        address="ул. Пушкина, 10",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)

    resp = await client.post(f"/api/v1/events/{event.id}/prepare-share", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "prepared_message_id" in data
    assert "expiration_date" in data
    assert data["prepared_message_id"] == f"mock_prep_{event.id}"


@pytest.mark.asyncio
async def test_02_prepare_share_nonexistent_event_404(client, auth_headers):
    """2. Nonexistent event returns 404 NOT FOUND."""
    resp = await client.post("/api/v1/events/non_existent_event_id/prepare-share", headers=auth_headers)
    assert resp.status_code == 404
    assert "не найдено" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_03_prepare_share_unpublished_pending_403(client, test_session, auth_headers):
    """3. Unpublished event (PENDING) returns 403 FORBIDDEN."""
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    event = Event(
        title="Pending Share Event",
        description="Pending event",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) + timedelta(days=5),
        venue_name="Pending Hall",
        address="ул. Пушкина, 10",
        organizer_user_id=org_user.id,
        status=EventStatus.PENDING.value
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)

    resp = await client.post(f"/api/v1/events/{event.id}/prepare-share", headers=auth_headers)
    assert resp.status_code == 403
    assert "недоступно для публикации" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_04_prepare_share_deleted_event_404(client, test_session, auth_headers):
    """4. Deleted event returns 404 NOT FOUND."""
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    event = Event(
        title="Deleted Share Event",
        description="Deleted event",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) + timedelta(days=5),
        venue_name="Deleted Hall",
        address="ул. Пушкина, 10",
        organizer_user_id=org_user.id,
        status=EventStatus.DELETED.value
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)

    resp = await client.post(f"/api/v1/events/{event.id}/prepare-share", headers=auth_headers)
    assert resp.status_code == 404
    assert "не найдено" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_05_prepare_share_unauthenticated_401(client):
    """5. Unauthenticated request returns 401 UNAUTHORIZED."""
    resp = await client.post("/api/v1/events/any_event_id/prepare-share")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_06_telegram_bot_api_receives_correct_user_id():
    """6. Telegram Bot API receives correct user_id matching current user."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_msg_123", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_101"
    event.title = "Festival 2026"
    event.is_free = True
    event.start_at = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)
    event.venue_name = "Central Park"
    event.city_name = "Москва"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            res = await save_prepared_inline_share_message(
                user_telegram_id=777888999,
                event=event,
                deep_link="https://t.me/Ivently_bot/app?startapp=event_evt_101"
            )
            assert res["prepared_message_id"] == "prep_msg_123"
            assert captured_payload.get("user_id") == 777888999


@pytest.mark.asyncio
async def test_07_telegram_bot_api_receives_correct_event_deep_link():
    """7. Telegram Bot API receives correct event deep link in inline keyboard button."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_link_1", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_link_test"
    event.title = "Jazz Night"
    event.is_free = False
    event.price_amount = 500
    event.price_currency = "RUB"
    event.start_at = datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc)
    event.venue_name = "Blue Note"
    event.city_name = "Санкт-Петербург"
    event.cover_image_url = None

    deep_link = "https://t.me/Ivently_bot/app?startapp=event_evt_link_test"

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(
                user_telegram_id=12345,
                event=event,
                deep_link=deep_link
            )

    keyboard = captured_payload["result"]["reply_markup"]["inline_keyboard"]
    button = keyboard[0][0]
    assert button["text"] == "Открыть событие 🧭"
    assert button["url"] == deep_link


@pytest.mark.asyncio
async def test_08_telegram_bot_api_allow_user_chats():
    """8. allow_user_chats is strictly True."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_1", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_chats"
    event.title = "Test"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(12345, event, "https://t.me/Ivently_bot/app")

    assert captured_payload["allow_user_chats"] is True


@pytest.mark.asyncio
async def test_09_telegram_bot_api_allow_group_chats():
    """9. allow_group_chats is strictly True."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_1", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_chats"
    event.title = "Test"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(12345, event, "https://t.me/Ivently_bot/app")

    assert captured_payload["allow_group_chats"] is True


@pytest.mark.asyncio
async def test_10_telegram_bot_api_allow_bot_chats_false():
    """10. allow_bot_chats is strictly False."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_1", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_chats"
    event.title = "Test"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(12345, event, "https://t.me/Ivently_bot/app")

    assert captured_payload["allow_bot_chats"] is False


@pytest.mark.asyncio
async def test_11_telegram_bot_api_allow_channel_chats_false():
    """11. allow_channel_chats is strictly False."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_1", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_chats"
    event.title = "Test"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(12345, event, "https://t.me/Ivently_bot/app")

    assert captured_payload["allow_channel_chats"] is False


@pytest.mark.asyncio
async def test_12_valid_cover_generates_photo_result():
    """12. Valid public cover image generates InlineQueryResultPhoto."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_photo", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_photo"
    event.title = "Art Exhibition"
    event.is_free = True
    event.start_at = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)
    event.venue_name = "Gallery"
    event.city_name = "Москва"
    event.cover_image_url = "https://cdn.ivently.ru/events/art.jpg"

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("app.services.telegram_bot.check_public_image_validity", return_value=True):
            with patch("httpx.AsyncClient.post", side_effect=mock_post):
                await save_prepared_inline_share_message(
                    12345,
                    event,
                    "https://t.me/Ivently_bot/app?startapp=event_evt_photo"
                )

    result = captured_payload["result"]
    assert result["type"] == "photo"
    assert result["photo_url"] == "https://cdn.ivently.ru/events/art.jpg"
    assert "caption" in result
    assert "Art Exhibition" in result["caption"]


@pytest.mark.asyncio
async def test_13_invalid_or_missing_cover_falls_back_to_article():
    """13. Missing or invalid cover image falls back to InlineQueryResultArticle."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_article", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_article"
    event.title = "Meetup"
    event.is_free = True
    event.start_at = datetime(2026, 12, 2, 19, 0, tzinfo=timezone.utc)
    event.venue_name = "Coworking"
    event.city_name = "Казань"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("app.services.telegram_bot.check_public_image_validity", return_value=False):
            with patch("httpx.AsyncClient.post", side_effect=mock_post):
                await save_prepared_inline_share_message(
                    12345,
                    event,
                    "https://t.me/Ivently_bot/app?startapp=event_evt_article"
                )

    result = captured_payload["result"]
    assert result["type"] == "article"
    assert "input_message_content" in result
    assert "message_text" in result["input_message_content"]
    assert "Meetup" in result["title"]


@pytest.mark.asyncio
async def test_14_telegram_bot_api_error_502(client, test_session, auth_headers):
    """14. Telegram Bot API error returns HTTP 502 with clean error."""
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    event = Event(
        title="Error Event",
        description="Event that triggers Telegram error",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) + timedelta(days=5),
        venue_name="Concert Hall",
        address="ул. Пушкина, 10",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)

    with patch(
        "app.api.v1.events.save_prepared_inline_share_message",
        side_effect=RuntimeError("Telegram API error: USER_ID_INVALID")
    ):
        resp = await client.post(f"/api/v1/events/{event.id}/prepare-share", headers=auth_headers)
        assert resp.status_code == 502
        data = resp.json()
        assert "Не удалось подготовить сообщение в Telegram" in data["detail"]
        assert "USER_ID_INVALID" in data["detail"]


@pytest.mark.asyncio
async def test_15_telegram_bot_token_not_leaked_into_logs(caplog):
    """15. Telegram Bot token is never leaked into logs or error messages."""
    secret_token = "SECRET_TELEGRAM_BOT_TOKEN_12345"
    caplog.set_level(logging.DEBUG)

    class MockErrorResponse:
        def json(self):
            return {"ok": False, "description": "Bad Request: chat not found"}

    async def mock_post(url, **kwargs):
        return MockErrorResponse()

    event = MagicMock()
    event.id = "evt_secret"
    event.title = "Secret Event"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", secret_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            try:
                await save_prepared_inline_share_message(
                    user_telegram_id=55555,
                    event=event,
                    deep_link="https://t.me/Ivently_bot/app"
                )
            except Exception as e:
                # Token must not appear in raised exception string
                assert secret_token not in str(e)

    # Token must not appear in any log record
    for record in caplog.records:
        assert secret_token not in record.message
        assert secret_token not in str(record.args)


@pytest.mark.asyncio
async def test_16_price_formatting_free_event():
    """16. Free event formats price as '🎟 Вход бесплатный' and never displays 'RUB'."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_free", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_free"
    event.title = "Free Workshop"
    event.is_free = True
    event.price_amount = 0
    event.price_currency = "RUB"
    event.start_at = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
    event.venue_name = "Library"
    event.city_name = "Москва"
    event.cover_image_url = "https://cdn.ivently.ru/events/free.jpg"

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(
                12345,
                event,
                "https://t.me/Ivently_bot/app?startapp=event_evt_free"
            )

    caption = captured_payload["result"]["caption"]
    assert "🎟 Вход бесплатный" in caption
    assert "RUB" not in caption


@pytest.mark.asyncio
async def test_17_price_formatting_paid_event():
    """17. Paid event formats price as '🎟 Вход: 500 ₽' using ruble symbol and never 'RUB'."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_paid", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_paid"
    event.title = "Concert"
    event.is_free = False
    event.price_amount = 500.0
    event.price_currency = "RUB"
    event.start_at = datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc)
    event.venue_name = "Club"
    event.city_name = "Санкт-Петербург"
    event.cover_image_url = "https://cdn.ivently.ru/events/paid.jpg"

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(
                12345,
                event,
                "https://t.me/Ivently_bot/app?startapp=event_evt_paid"
            )

    caption = captured_payload["result"]["caption"]
    assert "🎟 Вход: 500 ₽" in caption
    assert "RUB" not in caption


@pytest.mark.asyncio
async def test_18_price_formatting_unknown_price_omitted():
    """18. When price_amount is None and not free, price line is omitted entirely."""
    mock_token = "987654321:CUSTOM_TEST_TOKEN"
    captured_payload = {}

    class MockResponse:
        def json(self):
            return {"ok": True, "result": {"id": "prep_none", "expiration_date": 1799999999}}

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return MockResponse()

    event = MagicMock()
    event.id = "evt_none"
    event.title = "Private Gathering"
    event.is_free = False
    event.price_amount = None
    event.price_currency = None
    event.start_at = datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc)
    event.venue_name = "Lounge"
    event.city_name = "Москва"
    event.cover_image_url = None

    with patch.object(settings, "TELEGRAM_BOT_TOKEN", mock_token):
        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            await save_prepared_inline_share_message(
                12345,
                event,
                "https://t.me/Ivently_bot/app?startapp=event_evt_none"
            )

    text = captured_payload["result"]["input_message_content"]["message_text"]
    assert "Вход" not in text
    assert "RUB" not in text
    assert "💰" not in text


@pytest.mark.asyncio
async def test_19_inline_search_returns_photo_result(test_session):
    """19. Inline search (@Ivently_bot query) returns InlineQueryResultPhoto when event has cover image."""
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    event = Event(
        title="Rock Festival 2026",
        description="Epic music festival",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) + timedelta(days=7),
        venue_name="Stadium Arena",
        address="ул. Спортивная, 1",
        price_amount=1500.0,
        price_currency="RUB",
        cover_image_url="https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)

    query_payload = {
        "id": "query_test_19",
        "query": "Rock Festival",
        "from": {"id": 12345678}
    }
    answer = await handle_inline_query(test_session, query_payload)
    results = answer.get("results", [])
    assert len(results) >= 1
    target = next((r for r in results if r["id"] == f"event_{event.id}"), None)
    assert target is not None
    assert target["type"] == "photo"
    assert "photo_url" in target
    assert "thumbnail_url" in target
    assert "caption" in target
    assert "🎟 <b>Rock Festival 2026</b>" in target["caption"]
    assert "🎟 Вход: 1500 ₽" in target["caption"]
    assert "RUB" not in target["caption"]
    button = target["reply_markup"]["inline_keyboard"][0][0]
    assert button["text"] == "Открыть событие 🧭"
    assert f"startapp=event_{event.id}" in button["url"]


@pytest.mark.asyncio
async def test_20_inline_search_fastpath_returns_photo_result(test_session):
    """20. Fast-path lookup by event_<id> returns InlineQueryResultPhoto with unified button."""
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    event = Event(
        title="Modern Theater Show",
        description="Drama spectacle",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        venue_name="Drama Hall",
        address="ул. Театральная, 5",
        price_amount=0,
        cover_image_url="https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?w=800",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)

    query_payload = {
        "id": "query_test_20",
        "query": f"event_{event.id}",
        "from": {"id": 12345678}
    }
    answer = await handle_inline_query(test_session, query_payload)
    results = answer.get("results", [])
    assert len(results) == 1
    target = results[0]
    assert target["type"] == "photo"
    assert "photo_url" in target
    assert "🎟 <b>Modern Theater Show</b>" in target["caption"]
    assert "🎟 Вход бесплатный" in target["caption"]
    assert "RUB" not in target["caption"]
    button = target["reply_markup"]["inline_keyboard"][0][0]
    assert button["text"] == "Открыть событие 🧭"
    assert f"startapp=event_{event.id}" in button["url"]


@pytest.mark.asyncio
async def test_21_get_event_details_supports_event_prefix(test_session):
    """21. get_event_details defensively resolves even if passed with 'event_' prefix."""
    city = (await test_session.execute(select(City))).scalars().first()
    category = (await test_session.execute(select(Category))).scalars().first()
    org_user = (await test_session.execute(select(User))).scalars().first()

    event = Event(
        title="Prefix Support Event",
        description="Testing defensive prefix stripping",
        city_id=city.id,
        category_id=category.id,
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Venue 1",
        address="ул. Мира, 1",
        organizer_user_id=org_user.id,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)

    # Calling with 'event_' prefix should resolve successfully without 404
    details = await get_event_details(test_session, f"event_{event.id}")
    assert details.id == event.id
    assert details.title == "Prefix Support Event"

