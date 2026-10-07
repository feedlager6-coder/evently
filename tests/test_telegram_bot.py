import pytest
from app.services.telegram_bot import handle_inline_query, handle_private_message


@pytest.mark.asyncio
async def test_inline_query_returns_results(test_session):
    query_payload = {
        "id": "query_12345",
        "query": "мероприятия в Санкт-Петербурге",
        "from": {"id": 123456789, "first_name": "Alex"}
    }

    resp = await handle_inline_query(test_session, query_payload)
    assert resp["inline_query_id"] == "query_12345"
    results = resp["results"]
    assert len(results) > 0

    first_article = results[0]
    assert first_article["type"] == "article"
    assert "Санкт-Петербург" in first_article["description"]
    assert "reply_markup" in first_article
    assert "url" in first_article["reply_markup"]["inline_keyboard"][0][0]


@pytest.mark.asyncio
async def test_inline_query_empty_state_handled(test_session):
    # Query with non-existent events
    query_payload = {
        "id": "query_99999",
        "query": "выставки сегодня в Сочи",
        "from": {"id": 123456789}
    }

    resp = await handle_inline_query(test_session, query_payload)
    results = resp["results"]
    assert len(results) == 1
    assert results[0]["id"] == "empty_state"
    assert "нет подходящих событий" in results[0]["title"]


@pytest.mark.asyncio
async def test_inline_query_city_makhachkala(test_session):
    # Query with exact city name "Махачкала"
    query_payload = {
        "id": "query_mcx",
        "query": "Махачкала",
        "from": {"id": 123456789}
    }
    resp = await handle_inline_query(test_session, query_payload)
    results = resp["results"]
    assert len(results) > 0
    assert results[0]["id"] != "empty_state"
    # Verify events are in Makhachkala
    assert any("Махачкала" in r["description"] for r in results)


@pytest.mark.asyncio
async def test_inline_query_keyword_search(test_session):
    # Query by keyword "Tech"
    query_payload = {
        "id": "query_tech",
        "query": "Tech",
        "from": {"id": 123456789}
    }
    resp = await handle_inline_query(test_session, query_payload)
    results = resp["results"]
    assert len(results) > 0
    assert any("Tech" in r["title"] for r in results)


def test_private_start_command():
    msg = {
        "text": "/start",
        "chat": {"id": 12345},
        "from": {"id": 12345, "first_name": "Sam"}
    }
    reply = handle_private_message(msg)
    assert reply is not None
    assert "Добро пожаловать в Ivently" in reply["text"]
    
    # Check buttons: Mini App + switch_inline_query
    ikb = reply["reply_markup"]["inline_keyboard"]
    assert len(ikb) >= 2
    main_btn = ikb[0][0]
    assert main_btn["text"] == "🧭 Открыть Ivently"
    assert main_btn.get("style") == "primary"
    # Verify switch_inline_query button
    inline_btn_row = next((row for row in ikb if any("switch_inline_query" in b for b in row)), None)
    assert inline_btn_row is not None
    assert inline_btn_row[0]["switch_inline_query"] == ""


def test_private_create_command():
    msg = {
        "text": "/create",
        "chat": {"id": 12345},
        "from": {"id": 12345}
    }
    reply = handle_private_message(msg)
    assert reply is not None
    assert "Создание нового мероприятия" in reply["text"]


def test_private_admin_command_authorization():
    # 1. Admin user
    admin_msg = {
        "text": "/admin",
        "chat": {"id": 123456789},
        "from": {"id": 123456789}
    }
    admin_reply = handle_private_message(admin_msg)
    assert admin_reply is not None
    assert "Панель администратора Ivently" in admin_reply["text"]
    assert "123456789" in admin_reply["text"]


    # 2. Non-admin user
    non_admin_msg = {
        "text": "/admin",
        "chat": {"id": 999999999},
        "from": {"id": 999999999}
    }
    non_admin_reply = handle_private_message(non_admin_msg)
    assert non_admin_reply is not None
    assert "нет прав администратора" in non_admin_reply["text"]
    assert "999999999" in non_admin_reply["text"]


@pytest.mark.asyncio
async def test_telegram_webhook_endpoint(client):
    # Send simulated inline query webhook update
    update = {
        "update_id": 10001,
        "inline_query": {
            "id": "webhook_q1",
            "query": "мероприятия в Санкт-Петербурге",
            "from": {"id": 123456789}
        }
    }
    resp = await client.post("/api/v1/telegram/webhook", json=update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "answerInlineQuery"
    assert data["inline_query_id"] == "webhook_q1"
    assert len(data["results"]) > 0


@pytest.mark.asyncio
async def test_telegram_webhook_start_command(client):
    # Send simulated /start message to webhook
    update = {
        "update_id": 10002,
        "message": {
            "message_id": 1,
            "chat": {"id": 98765, "type": "private"},
            "from": {"id": 98765, "first_name": "TestUser"},
            "text": "/start"
        }
    }
    resp = await client.post("/api/v1/telegram/webhook", json=update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "sendMessage"
    assert data["chat_id"] == 98765
    assert "Добро пожаловать в Ivently" in data["text"]
    assert "reply_markup" in data
    assert "inline_keyboard" in data["reply_markup"]
    assert len(data["reply_markup"]["inline_keyboard"]) >= 2


@pytest.mark.asyncio
async def test_telegram_webhook_start_with_deep_link(client):
    # Send /start event_123 deep-link to webhook
    update = {
        "update_id": 10003,
        "message": {
            "message_id": 2,
            "chat": {"id": 98765, "type": "private"},
            "from": {"id": 98765, "first_name": "TestUser"},
            "text": "/start event_spb_jazz"
        }
    }
    resp = await client.post("/api/v1/telegram/webhook", json=update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "sendMessage"
    assert data["chat_id"] == 98765
    button = data["reply_markup"]["inline_keyboard"][0][0]
    btn_url = button.get("url") or button.get("web_app", {}).get("url", "")
    assert "event_spb_jazz" in btn_url


@pytest.mark.asyncio
async def test_telegram_webhook_help_and_fallback(client):
    # 1. /help
    help_update = {
        "update_id": 10004,
        "message": {
            "message_id": 3,
            "chat": {"id": 98765, "type": "private"},
            "from": {"id": 98765, "first_name": "TestUser"},
            "text": "/help"
        }
    }
    resp = await client.post("/api/v1/telegram/webhook", json=help_update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "sendMessage"
    assert "Как пользоваться Ivently" in data["text"]

    # 2. General text message fallback
    msg_update = {
        "update_id": 10005,
        "message": {
            "message_id": 4,
            "chat": {"id": 98765, "type": "private"},
            "from": {"id": 98765, "first_name": "TestUser"},
            "text": "Привет! Что интересного сегодня?"
        }
    }
    resp2 = await client.post("/api/v1/telegram/webhook", json=msg_update)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["method"] == "sendMessage"
    assert "Привет!" in data2["text"]


@pytest.mark.asyncio
async def test_telegram_info_diagnostics_endpoint(client):
    resp = await client.get("/api/v1/telegram/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "bot_configured" in data
    assert "bot_username" in data
    assert "effective_public_host" in data
    assert "expected_webhook_url" in data


@pytest.mark.asyncio
async def test_inline_query_direct_event_lookup(test_session):
    from sqlalchemy import select
    from app.models.event import Event, EventStatus
    event = (await test_session.execute(select(Event).where(Event.status == EventStatus.PUBLISHED.value).limit(1))).scalar_one_or_none()
    assert event is not None

    query_payload = {
        "id": "query_direct_event",
        "query": f"event_{event.id}",
        "from": {"id": 123456789, "first_name": "Friend"}
    }
    resp = await handle_inline_query(test_session, query_payload)
    assert resp["inline_query_id"] == "query_direct_event"
    assert len(resp["results"]) == 1
    item = resp["results"][0]
    assert item["id"] == f"event_{event.id}"
    assert event.title in item["title"]
    assert "🧭 Открыть в Mini App" in str(item["reply_markup"])
    assert f"startapp=event_{event.id}" in str(item["reply_markup"])

