import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.organization import Organization
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastType,
    BroadcastTargetType,
    BroadcastTemplateKey,
    BroadcastStatus,
)
from app.services.broadcast_service import (
    preview_broadcast,
    format_broadcast_content,
    create_broadcast,
)
from app.services.event_service import (
    create_organizer_event,
    update_organizer_event,
    get_event_details,
    list_published_events,
)
from app.schemas.event import EventCreate, EventUpdate
from app.schemas.broadcast import BroadcastPreviewRequest, BroadcastCreateRequest


@pytest.mark.asyncio
async def test_d507_01_broadcast_custom_text_500_limit(client, test_session):
    """
    Direction 1: Broadcast custom_text limit increased from 300 to 500 chars.
    - 500 chars accepted on preview and create
    - 501 chars rejected (422)
    - Full caption <= 1024 chars for Telegram photo send
    """
    owner_id = 907101
    auth_headers = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_d507')}"}

    u = User(id=owner_id, telegram_id=owner_id, username="owner_d507")
    org = Organization(id="org_d507_1", name="Театр Д507", slug="teatr-d507-1", category="Театр", city_id="makhachkala", owner_user_id=owner_id)
    ev = Event(
        id="ev_d507_1",
        title="Спектакль сезона",
        description="Большой вечер в театре",
        category_id="theatre",
        city_id="makhachkala",
        organization_id=org.id,
        organizer_user_id=owner_id,
        start_at=datetime(2026, 11, 10, 19, 0, tzinfo=timezone.utc),
        venue_name="Основная сцена",
        address="ул. Пушкина, д. 10",
        status=EventStatus.PUBLISHED.value,
        cover_image_url="https://images.unsplash.com/photo-test.jpg",
    )
    test_session.add_all([u, org, ev])
    await test_session.commit()

    # 1. 500 characters string
    text_500 = "А" * 500
    assert len(text_500) == 500

    # Preview with 500 chars via service
    preview = await preview_broadcast(
        session=test_session,
        organizer_user_id=owner_id,
        organization_id=org.id,
        target_type=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        broadcast_type=BroadcastType.MARKETING.value,
        template_key=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        event_id=ev.id,
        custom_text=text_500,
    )
    assert text_500 in preview.preview_text

    # Verify formatted telegram caption length <= 1024
    content, btn_text, btn_url = format_broadcast_content(
        organization=org,
        template_key=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        event=ev,
        custom_text=text_500,
    )
    assert len(content) <= 1024, f"Caption length {len(content)} exceeds 1024 limit"

    # API Preview with 500 chars via /api/v1/organizer/broadcasts/preview
    resp = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        headers=auth_headers,
        json={
            "organization_id": org.id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": ev.id,
            "custom_text": text_500,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert text_500 in data["preview_text"]

    # 2. 501 characters rejected by schema (422)
    text_501 = "Б" * 501
    resp_501 = await client.post(
        "/api/v1/organizer/broadcasts/preview",
        headers=auth_headers,
        json={
            "organization_id": org.id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": ev.id,
            "custom_text": text_501,
        },
    )
    assert resp_501.status_code == 422

    # API Create with 501 chars rejected (422)
    resp_create_501 = await client.post(
        "/api/v1/organizer/broadcasts",
        headers=auth_headers,
        json={
            "organization_id": org.id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": ev.id,
            "custom_text": text_501,
        },
    )
    assert resp_create_501.status_code == 422


@pytest.mark.asyncio
async def test_d507_02_organizer_privacy_default_hidden(client, test_session):
    """
    Direction 2: Default allow_event_contact = False.
    Telegram username/handle/CTA hidden by default for personal events.
    """
    user_id = 907201
    auth_headers = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='secret_organizer', first_name='Рустам')}"}

    u = User(id=user_id, telegram_id=user_id, username="secret_organizer", first_name="Рустам")
    test_session.add(u)
    await test_session.commit()

    # Create personal event via API (without allow_event_contact)
    create_payload = {
        "title": "Утренний забег в парке",
        "description": "Собираемся в 8:00 утра на разминку.",
        "category_id": "sports",
        "city_id": "makhachkala",
        "start_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "venue_name": "Парк Ленинского комсомола",
        "price_amount": 0,
    }
    resp = await client.post("/api/v1/events", headers=auth_headers, json=create_payload)
    assert resp.status_code == 201
    data = resp.json()

    # Privacy verification:
    assert data["allow_event_contact"] is False
    assert data["organizer_username"] is None
    assert data["organizer_contact_url"] is None
    # organizer_name shows first_name ("Рустам"), not @secret_organizer
    assert data["organizer_name"] == "Рустам"
    assert "secret_organizer" not in (data["organizer_name"] or "")


@pytest.mark.asyncio
async def test_d507_03_organizer_privacy_opt_in_contact(client, test_session):
    """
    Direction 2: When allow_event_contact = True, organizer contact is visible.
    Toggling allow_event_contact via update modifies contact availability.
    """
    user_id = 907301
    auth_headers = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='open_organizer', first_name='Камиль')}"}

    u = User(id=user_id, telegram_id=user_id, username="open_organizer", first_name="Камиль")
    test_session.add(u)
    await test_session.commit()

    # 1. Create with allow_event_contact = True
    create_payload = {
        "title": "Открытый шахматный турнир",
        "description": "Турнир для всех желающих, регистрация на месте.",
        "category_id": "sports",
        "city_id": "makhachkala",
        "start_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
        "venue_name": "Шахматный клуб",
        "allow_event_contact": True,
    }
    resp = await client.post("/api/v1/events", headers=auth_headers, json=create_payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["allow_event_contact"] is True
    assert data["organizer_username"] == "open_organizer"
    assert data["organizer_contact_url"] == "https://t.me/open_organizer"
    event_id = data["id"]

    # 2. Update event to turn off contact permission
    patch_resp = await client.patch(
        f"/api/v1/events/{event_id}",
        headers=auth_headers,
        json={"allow_event_contact": False},
    )
    assert patch_resp.status_code == 200
    patched_data = patch_resp.json()
    assert patched_data["allow_event_contact"] is False
    assert patched_data["organizer_username"] is None
    assert patched_data["organizer_contact_url"] is None
    assert patched_data["organizer_name"] == "Камиль"


@pytest.mark.asyncio
async def test_d507_04_organization_events_privacy_isolation(client, test_session):
    """
    Direction 2: Organization events display organization details,
    never leaking personal owner username/links regardless of allow_event_contact.
    """
    owner_id = 907401
    auth_headers = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='org_owner_private', first_name='Мурад')}"}

    u = User(id=owner_id, telegram_id=owner_id, username="org_owner_private", first_name="Мурад")
    org = Organization(id="org_d507_priv", name="Академия Спорта", slug="akademiya-sporta", category="Спорт", city_id="makhachkala", owner_user_id=owner_id)
    test_session.add_all([u, org])
    await test_session.commit()

    create_payload = {
        "title": "Мастер-класс по боксу",
        "description": "Открытая тренировка от Академии Спорта.",
        "category_id": "sports",
        "city_id": "makhachkala",
        "organization_id": org.id,
        "start_at": (datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
        "venue_name": "Зал бокса",
        "allow_event_contact": True,
    }
    resp = await client.post("/api/v1/events", headers=auth_headers, json=create_payload)
    assert resp.status_code == 201
    data = resp.json()

    # For organization events, organizer_name is organization name, no personal telegram link
    assert data["organizer_name"] == "Академия Спорта"
    assert data["organizer_username"] is None
    assert data["organizer_contact_url"] is None
    assert "org_owner_private" not in (data["organizer_name"] or "")


@pytest.mark.asyncio
async def test_d507_05_event_source_fields_default_and_readiness(test_session):
    """
    Direction 4: Event model prepared for future external sources.
    Defaults to source_type="user", all external sync fields nullable.
    """
    user_id = 907501
    u = User(id=user_id, telegram_id=user_id, username="user_d507_src")
    ev_user = Event(
        id="ev_d507_src_user",
        title="Пользовательское событие",
        description="Создано вручную пользователем",
        category_id="education",
        city_id="makhachkala",
        organizer_user_id=user_id,
        start_at=datetime.now(timezone.utc) + timedelta(days=5),
        venue_name="Лофт",
        address="ул. Ленина, д. 15",
        status=EventStatus.PUBLISHED.value,
    )
    # External event schema readiness test (e.g. prepared for future external sync)
    ev_external = Event(
        id="ev_d507_src_ext",
        title="Концерт внешней афиши",
        description="Импортированное событие",
        category_id="concerts",
        city_id="moscow",
        organizer_user_id=user_id,
        start_at=datetime.now(timezone.utc) + timedelta(days=6),
        venue_name="Крокус",
        address="Крокус Сити Холл",
        status=EventStatus.PUBLISHED.value,
        source_type="yandex_afisha",
        source_name="Яндекс Афиша",
        external_id="ya_concert_12345",
        source_url="https://afisha.yandex.ru/events/12345",
        last_synced_at=datetime.now(timezone.utc),
    )
    test_session.add_all([u, ev_user, ev_external])
    await test_session.commit()

    # Verify default source_type
    res_user = await test_session.execute(select(Event).where(Event.id == ev_user.id))
    loaded_user_ev = res_user.scalar_one()
    assert loaded_user_ev.source_type == "user"
    assert loaded_user_ev.source_name is None
    assert loaded_user_ev.external_id is None
    assert loaded_user_ev.source_url is None
    assert loaded_user_ev.last_synced_at is None

    # Verify external event fields
    res_ext = await test_session.execute(select(Event).where(Event.id == ev_external.id))
    loaded_ext_ev = res_ext.scalar_one()
    assert loaded_ext_ev.source_type == "yandex_afisha"
    assert loaded_ext_ev.source_name == "Яндекс Афиша"
    assert loaded_ext_ev.external_id == "ya_concert_12345"
    assert loaded_ext_ev.source_url == "https://afisha.yandex.ru/events/12345"
    assert loaded_ext_ev.last_synced_at is not None

    # Verify get_event_details returns source fields
    details_user = await get_event_details(test_session, ev_user.id)
    assert details_user.source_type == "user"
    assert details_user.source_name is None
    assert details_user.external_id is None

    details_ext = await get_event_details(test_session, ev_external.id)
    assert details_ext.source_type == "yandex_afisha"
    assert details_ext.source_name == "Яндекс Афиша"
    assert details_ext.external_id == "ya_concert_12345"


@pytest.mark.asyncio
async def test_d507_06_cities_endpoint_and_filtering(client):
    """
    Direction 3: Active cities retrieval and search query filtering.
    """
    resp = await client.get("/api/v1/cities")
    assert resp.status_code == 200
    cities = resp.json()
    assert len(cities) >= 20

    # Search for Makhachkala
    resp_search = await client.get("/api/v1/cities?q=махачкала")
    assert resp_search.status_code == 200
    search_results = resp_search.json()
    assert len(search_results) >= 1
    assert any(c["id"] == "makhachkala" for c in search_results)
