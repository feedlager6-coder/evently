import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.event import Event, EventStatus
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.services.discovery_service import discovery_service, transliterate_latin_to_cyrillic
from app.services.telegram_bot import handle_inline_query
from tests.conftest import make_test_init_data


@pytest.mark.asyncio
async def test_transliterate_latin_to_cyrillic():
    assert transliterate_latin_to_cyrillic("makhachkala") == "махачкала"
    assert transliterate_latin_to_cyrillic("derbent") == "дербент"
    assert transliterate_latin_to_cyrillic("moscow") == "москва"
    assert transliterate_latin_to_cyrillic("spb") == "санкт-петербург"
    assert transliterate_latin_to_cyrillic("jazz") is not None
    # Empty or cyrillic returns None
    assert transliterate_latin_to_cyrillic("") is None
    assert transliterate_latin_to_cyrillic("махачкала") is None


@pytest.mark.asyncio
async def test_discovery_search_events_and_venues(client: AsyncClient, test_session: AsyncSession):
    # Setup test organization and published event
    user = User(
        id=991122,
        telegram_id=991122,
        first_name="Discovery",
        username="discovery_tester"
    )
    test_session.add(user)
    await test_session.flush()

    org = Organization(
        id="org_discovery_venue_test",
        owner_user_id=user.id,
        name="Loft Hall Caspian",
        slug="loft-hall-caspian",
        category="Концертная площадка",
        city_id="makhachkala",
        address="ул. Приморская, 15",
        status=OrganizationStatus.ACTIVE.value,
        is_verified=True
    )
    test_session.add(org)

    event_published = Event(
        id="ev_discovery_1",
        title="Большой Акустический Концерт",
        description="Уникальный живой концерт в атмосферном лофте на берегу моря.",
        category_id="concerts",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Loft Hall Caspian",
        address="ул. Приморская, 15",
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=user.id,
        organization_id=org.id,
        price_amount=1000.0,
        price_currency="RUB"
    )
    # Draft event (should NOT be visible)
    event_draft = Event(
        id="ev_discovery_draft",
        title="Секретный Акустический Джем",
        description="Неопубликованная репетиция.",
        category_id="concerts",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        venue_name="Loft Hall Caspian",
        address="ул. Приморская, 15",
        status=EventStatus.PENDING.value,
        organizer_user_id=user.id,
        organization_id=org.id
    )
    test_session.add_all([event_published, event_draft])
    await test_session.commit()

    # 1. Search by keyword "Акустический"
    res = await discovery_service.unified_search(
        session=test_session,
        query="Акустический",
        city_id="makhachkala"
    )
    assert res.total_events >= 1
    found_event_ids = [e.id for e in res.events]
    assert "ev_discovery_1" in found_event_ids
    assert "ev_discovery_draft" not in found_event_ids  # Security: draft excluded

    # 2. Search by venue/place name "Loft Hall"
    res_venue = await discovery_service.unified_search(
        session=test_session,
        query="Loft Hall",
        city_id="makhachkala"
    )
    assert res_venue.total_venues >= 1
    v = next((v for v in res_venue.venues if "Loft Hall" in v.name), None)
    assert v is not None
    assert v.organization_id == "org_discovery_venue_test"
    assert v.upcoming_events_count >= 1

    # 3. Search by organization name "Caspian"
    res_org = await discovery_service.unified_search(
        session=test_session,
        query="Caspian",
        city_id="makhachkala"
    )
    assert res_org.total_organizations >= 1
    o = next((o for o in res_org.organizations if o.id == "org_discovery_venue_test"), None)
    assert o is not None
    assert o.name == "Loft Hall Caspian"
    assert o.is_verified is True


@pytest.mark.asyncio
async def test_discovery_endpoint_http(client: AsyncClient, test_session: AsyncSession):
    # Test HTTP endpoint
    resp = await client.get("/api/v1/discovery/search?q=Акустический&city_id=makhachkala")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "organizations" in data
    assert "venues" in data
    assert "total_events" in data
    assert "total_organizations" in data
    assert "total_venues" in data
    assert data["query"] == "Акустический"
    assert data["city_id"] == "makhachkala"

    # Verify no private data leaked in organizations or events
    for org in data["organizations"]:
        assert "owner_user_id" not in org
    for ev in data["events"]:
        assert "rejection_reason" not in ev
        assert "organizer_user_id" not in ev


@pytest.mark.asyncio
async def test_discovery_transliteration_and_case(client: AsyncClient, test_session: AsyncSession):
    # Test case-insensitivity and transliteration with Latin query
    resp = await client.get("/api/v1/discovery/search?q=makhachkala")
    assert resp.status_code == 200
    data = resp.json()
    assert data["city_id"] == "makhachkala"


@pytest.mark.asyncio
async def test_telegram_inline_search_includes_orgs(test_session: AsyncSession):
    user = User(
        id=992233,
        telegram_id=992233,
        first_name="InlineTester",
        username="inline_tester"
    )
    test_session.add(user)
    await test_session.flush()

    org = Organization(
        id="org_inline_test_1",
        owner_user_id=user.id,
        name="Loft Hall Space",
        slug="loft-hall-space",
        category="Концертная площадка",
        city_id="makhachkala",
        status=OrganizationStatus.ACTIVE.value
    )
    test_session.add(org)
    await test_session.commit()

    # Query with matching organization
    payload = {
        "id": "inline_query_999",
        "query": "Loft Hall",
        "from": {"id": 12345}
    }
    resp = await handle_inline_query(test_session, payload)
    assert resp["inline_query_id"] == "inline_query_999"
    results = resp["results"]
    assert len(results) >= 1
    # Check that org result is included
    org_item = next((r for r in results if r["id"].startswith("org_")), None)
    assert org_item is not None
    assert "Loft Hall" in org_item["title"]
    assert "reply_markup" in org_item
