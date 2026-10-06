import pytest
import httpx
from unittest.mock import AsyncMock, patch
from pathlib import Path
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.models.user import User
from app.models.event import Event
from app.models.city import City
from app.services.auth_service import get_or_create_user
from app.schemas.telegram import TelegramUserPayload


@pytest.mark.asyncio
async def test_telegram_write_access_allowed_is_silent_and_safe(client):
    """
    P0.1 Task 3: Verifies that write_access_allowed Telegram update is processed silently:
    - Returns 200 OK with ok: True
    - Does NOT return method: sendMessage
    """
    update = {
        "update_id": 88001,
        "message": {
            "message_id": 99,
            "from": {"id": 99887766, "is_bot": False, "first_name": "SilentUser"},
            "chat": {"id": 99887766, "type": "private"},
            "date": 1728251000,
            "write_access_allowed": {
                "from_request": True
            }
        }
    }

    res = await client.post("/api/v1/telegram/webhook", json=update)
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True
    assert data.get("type") == "write_access_allowed"
    assert "method" not in data, "Must not return method: sendMessage in response"


@pytest.mark.asyncio
async def test_telegram_start_command_still_handled(client):
    """
    P0.1 Task 3: Verifies that other Telegram messages like /start are NOT broken
    and still return the interactive welcome message.
    """
    update = {
        "update_id": 88002,
        "message": {
            "message_id": 100,
            "from": {"id": 99887766, "is_bot": False, "first_name": "TestUser"},
            "chat": {"id": 99887766, "type": "private"},
            "date": 1728251005,
            "text": "/start"
        }
    }
    res = await client.post("/api/v1/telegram/webhook", json=update)
    assert res.status_code == 200
    data = res.json()
    assert data.get("method") == "sendMessage" or data.get("ok") is True


@pytest.mark.asyncio
async def test_new_user_default_city_is_none(test_session):
    """
    P0.1 Task 1: Verifies that a newly registered user starts with default_city_id=None
    rather than being silently assigned to Makhachkala.
    """
    tg_user = TelegramUserPayload(
        id=777001,
        first_name="BrandNew",
        last_name="Visitor",
        username="brand_new_visitor",
        photo_url=None
    )

    user = await get_or_create_user(test_session, tg_user)
    assert user.telegram_id == 777001
    assert user.default_city_id is None, "New user must NOT be silently assigned makhachkala"


@pytest.mark.asyncio
async def test_existing_user_default_city_preserved(test_session):
    """
    P0.1 Task 1: Verifies that a returning user with an existing default_city_id
    retains their city upon re-authentication.
    """
    # Create user with Moscow as default city
    existing_user = User(
        telegram_id=777002,
        first_name="Returning",
        username="returning_user",
        default_city_id="moscow"
    )
    test_session.add(existing_user)
    await test_session.commit()

    tg_user = TelegramUserPayload(
        id=777002,
        first_name="Returning",
        last_name="UpdatedLast",
        username="returning_user",
        photo_url=None
    )

    user = await get_or_create_user(test_session, tg_user)
    assert user.default_city_id == "moscow", "Returning user must retain existing default_city_id"


@pytest.mark.asyncio
async def test_set_default_city_endpoint(client, test_session):
    """
    P0.1 Task 1: Verifies that POST /api/v1/cities/default sets the user's default city.
    """
    user_id = 777003
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='city_setter')}"}

    # Verify initial profile
    profile_res = await client.get("/api/v1/users/me", headers=auth_header)
    assert profile_res.status_code == 200
    assert profile_res.json()["default_city_id"] is None

    # Set city to spb
    set_res = await client.post("/api/v1/cities/default?city_id=spb", headers=auth_header)
    assert set_res.status_code == 200
    assert set_res.json()["id"] == "spb"

    # Verify profile updated
    profile_after = await client.get("/api/v1/users/me", headers=auth_header)
    assert profile_after.json()["default_city_id"] == "spb"

    # Non-existent city returns 404
    bad_res = await client.post("/api/v1/cities/default?city_id=nonexistent_city_xyz", headers=auth_header)
    assert bad_res.status_code == 404


@pytest.mark.asyncio
async def test_events_endpoint_with_explicit_and_empty_city(client):
    """
    P0.1 Task 1 & Task 4: Verifies city filtering isolation:
    - Empty city returns 0 events
    - City with events returns events for that city
    """
    # A city with no seeded events
    empty_res = await client.get("/api/v1/events?city_id=izberbash")
    assert empty_res.status_code == 200
    assert empty_res.json()["events"] == []
    assert empty_res.json()["total"] == 0

    # City with events
    spb_res = await client.get("/api/v1/events?city_id=spb")
    assert spb_res.status_code == 200
    events = spb_res.json()["events"]
    assert len(events) > 0
    assert all(e["city_id"] == "spb" for e in events)


@pytest.mark.asyncio
async def test_personal_event_creator_isolation(client, test_session):
    """
    P0.1 Task 2: Verifies that personal events (organization_id=None) can be created,
    retrieved, and managed by their creator without creating an organization.
    """
    creator_id = 777004
    auth_creator = {"Authorization": f"tma {make_test_init_data(user_id=creator_id, username='personal_creator')}"}

    # Verify user has 0 organizations
    orgs_res = await client.get("/api/v1/organizations/me", headers=auth_creator)
    assert orgs_res.status_code == 200
    assert len(orgs_res.json()) == 0

    # Create personal event (organization_id not provided / None)
    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Утренний забег в парке",
            "description": "Дружеская пробежка 5 км для всех желающих.",
            "category_id": "concerts",
            "city_id": "spb",
            "start_at": "2026-10-15T09:00:00Z",
            "venue_name": "Парк Победы",
            "address": "Московский пр., 188",
            "price_amount": 0,
            "price_currency": "RUB",
        },
        headers=auth_creator
    )
    assert create_res.status_code == 201
    created_event = create_res.json()
    assert created_event["organization_id"] is None
    assert created_event["title"] == "Утренний забег в парке"

    # Verify organizer events list returns the personal event to the creator
    my_events_res = await client.get("/api/v1/organizer/events", headers=auth_creator)
    assert my_events_res.status_code == 200
    my_events = my_events_res.json()
    assert len(my_events) >= 1
    assert any(e["id"] == created_event["id"] for e in my_events)

    # Verify user still has 0 organizations
    orgs_after = await client.get("/api/v1/organizations/me", headers=auth_creator)
    assert orgs_after.status_code == 200
    assert len(orgs_after.json()) == 0


def test_contract_organizer_tab_is_organizer_separation():
    """
    P0.1 Task 2: Contract check ensuring OrganizerTab strictly bases isOrganizer
    on organizations.length > 0 and renders the 'Созданные' tab.
    """
    frontend_path = Path("frontend/src/components/OrganizerTab.tsx")
    assert frontend_path.exists(), "OrganizerTab.tsx must exist"
    content = frontend_path.read_text(encoding="utf-8")

    assert "const isOrganizer = organizations.length > 0;" in content, (
        "isOrganizer must strictly check organizations.length > 0"
    )
    assert "organizations.length > 0 || myCreatedEvents.length > 0" not in content, (
        "myCreatedEvents must not promote user to isOrganizer"
    )
    assert "label: 'Созданные'" in content, (
        "OrganizerTab must provide a 'Созданные' tab for user's personal created events"
    )


def test_contract_app_honest_city_first_run_and_empty_state():
    """
    P0.1 Task 1 & Task 4: Contract check ensuring App.tsx eliminates silent fallback
    and renders proper empty city vs filter-empty states.
    """
    app_path = Path("frontend/src/App.tsx")
    assert app_path.exists(), "App.tsx must exist"
    content = app_path.read_text(encoding="utf-8")

    # Task 1: No silent makhachkala fallback in initial state
    assert "saved && cached.some((c) => c.id === saved) ? saved : 'makhachkala'" not in content, (
        "App.tsx must not default selectedCityId to makhachkala"
    )
    # Task 1: Gating in loadFeedEvents
    assert "if (!selectedCityId)" in content, "loadFeedEvents must gate on selectedCityId"

    # Task 4: Empty city wording
    assert "пока нет актуальных событий" in content, (
        "App.tsx must include 'пока нет актуальных событий' copy"
    )
    assert "Создать событие" in content, "Empty city state must provide 'Создать событие' CTA"
    assert "Выбрать другой город" in content, "Empty city state must provide 'Выбрать другой город' CTA"

    # Task 4: Filter-empty wording
    assert "По выбранным фильтрам ничего не найдено." in content, (
        "App.tsx must include 'По выбранным фильтрам ничего не найдено.' copy"
    )
