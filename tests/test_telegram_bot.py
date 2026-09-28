import pytest
from app.services.telegram_bot import handle_inline_query, handle_private_message


@pytest.mark.asyncio
async def test_inline_query_returns_results(test_session):
    query_payload = {
        "id": "query_12345",
        "query": "концерты в Варшаве",
        "from": {"id": 123456789, "first_name": "Alex"}
    }

    resp = await handle_inline_query(test_session, query_payload)
    assert resp["inline_query_id"] == "query_12345"
    results = resp["results"]
    assert len(results) > 0

    first_article = results[0]
    assert first_article["type"] == "article"
    assert "Варшава" in first_article["description"]
    assert "reply_markup" in first_article
    assert "url" in first_article["reply_markup"]["inline_keyboard"][0][0]


@pytest.mark.asyncio
async def test_inline_query_empty_state_handled(test_session):
    # Query with non-existent events
    query_payload = {
        "id": "query_99999",
        "query": "спорт сегодня в Варшаве",
        "from": {"id": 123456789}
    }

    resp = await handle_inline_query(test_session, query_payload)
    results = resp["results"]
    assert len(results) == 1
    assert results[0]["id"] == "empty_state"
    assert "нет подходящих событий" in results[0]["title"]


def test_private_start_command():
    msg = {
        "text": "/start",
        "chat": {"id": 12345},
        "from": {"id": 12345, "first_name": "Sam"}
    }
    reply = handle_private_message(msg)
    assert reply is not None
    assert "Добро пожаловать в Evently" in reply["text"]
    assert len(reply["reply_markup"]["inline_keyboard"]) >= 1


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
    assert "Панель администратора Evently" in admin_reply["text"]

    # 2. Non-admin user
    non_admin_msg = {
        "text": "/admin",
        "chat": {"id": 999999999},
        "from": {"id": 999999999}
    }
    non_admin_reply = handle_private_message(non_admin_msg)
    assert non_admin_reply is not None
    assert "нет прав администратора" in non_admin_reply["text"]


@pytest.mark.asyncio
async def test_telegram_webhook_endpoint(client):
    # Send simulated inline query webhook update
    update = {
        "update_id": 10001,
        "inline_query": {
            "id": "webhook_q1",
            "query": "мероприятия в Варшаве",
            "from": {"id": 123456789}
        }
    }
    resp = await client.post("/api/v1/telegram/webhook", json=update)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["type"] == "inline_query"
    assert data["payload"]["method"] == "answerInlineQuery"
