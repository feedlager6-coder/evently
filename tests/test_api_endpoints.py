from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from tests.conftest import make_test_init_data
from app.services.event_service import get_city_timezone_range


@pytest.mark.asyncio
async def test_cities_and_categories_endpoints(client):
    # Cities
    cities_resp = await client.get("/api/v1/cities")
    assert cities_resp.status_code == 200
    cities = cities_resp.json()
    assert len(cities) >= 3
    city_ids = [c["id"] for c in cities]
    assert "warsaw" in city_ids
    assert "makhachkala" in city_ids
    assert "moscow" in city_ids

    # Categories
    cat_resp = await client.get("/api/v1/categories")
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    assert len(categories) == 7
    slugs = [c["slug"] for c in categories]
    assert "concerts" in slugs
    assert "sports" in slugs


@pytest.mark.asyncio
async def test_events_discovery_filtering(client):
    # 1. Warsaw events
    waw_resp = await client.get("/api/v1/events?city_id=warsaw")
    assert waw_resp.status_code == 200
    data = waw_resp.json()
    assert data["city_id"] == "warsaw"
    assert len(data["events"]) >= 10

    # 2. Warsaw concerts filter
    concerts_resp = await client.get("/api/v1/events?city_id=warsaw&category_id=concerts")
    assert concerts_resp.status_code == 200
    c_data = concerts_resp.json()
    assert len(c_data["events"]) >= 1
    for ev in c_data["events"]:
        assert ev["category_id"] == "concerts"


@pytest.mark.asyncio
async def test_event_details_and_rsvp_api_flow(client):
    # Discover first Warsaw event
    waw_resp = await client.get("/api/v1/events?city_id=warsaw")
    event_id = waw_resp.json()["events"][0]["id"]

    # Authenticate user
    init_data = make_test_init_data(user_id=444555666, username="event_goer")
    headers = {"Authorization": f"tma {init_data}"}

    # 1. Get Details before RSVP
    det_1 = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert det_1.status_code == 200
    assert det_1.json()["is_attending"] is False
    initial_count = det_1.json()["attendee_count"]

    # 2. POST RSVP (Create attendance)
    rsvp_post = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=headers)
    assert rsvp_post.status_code == 200
    assert rsvp_post.json()["is_attending"] is True
    assert rsvp_post.json()["attendee_count"] == initial_count + 1

    # 3. Repeat POST RSVP (Idempotent check)
    rsvp_repeat = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=headers)
    assert rsvp_repeat.status_code == 200
    assert rsvp_repeat.json()["is_attending"] is True
    assert rsvp_repeat.json()["attendee_count"] == initial_count + 1

    # 4. Details now shows is_attending=True
    det_2 = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert det_2.json()["is_attending"] is True

    # 5. DELETE RSVP (Cancel attendance)
    rsvp_del = await client.delete(f"/api/v1/events/{event_id}/rsvp", headers=headers)
    assert rsvp_del.status_code == 200
    assert rsvp_del.json()["is_attending"] is False
    assert rsvp_del.json()["attendee_count"] == initial_count

    # 6. Repeat DELETE RSVP (Idempotent safe check)
    rsvp_del_repeat = await client.delete(f"/api/v1/events/{event_id}/rsvp", headers=headers)
    assert rsvp_del_repeat.status_code == 200
    assert rsvp_del_repeat.json()["is_attending"] is False
    assert rsvp_del_repeat.json()["attendee_count"] == initial_count


@pytest.mark.asyncio
async def test_organizer_and_admin_end_to_end_flow(client):
    # 1. Organizer submits event
    org_init = make_test_init_data(user_id=111222333, username="cool_organizer")
    org_headers = {"Authorization": f"tma {org_init}"}

    now = datetime.now(timezone.utc)
    event_payload = {
        "title": "Warsaw Underground Rave 2026",
        "description": "Hard techno and acid trance in an industrial warehouse.",
        "cover_image_url": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30",
        "category_id": "parties",
        "city_id": "warsaw",
        "start_at": (now + timedelta(days=5)).isoformat(),
        "venue_name": "Warehouse 7",
        "address": "ul. Przemysłowa 5",
        "price_amount": 60.0,
        "price_currency": "PLN"
    }

    create_resp = await client.post("/api/v1/events", json=event_payload, headers=org_headers)
    assert create_resp.status_code == 201
    created_event = create_resp.json()
    event_id = created_event["id"]
    assert created_event["status"] == "pending"

    # Organizer sees it in /organizer/events
    my_events_resp = await client.get("/api/v1/organizer/events", headers=org_headers)
    assert my_events_resp.status_code == 200
    assert any(e["id"] == event_id for e in my_events_resp.json())

    # Regular public discovery does NOT show pending event
    public_resp = await client.get("/api/v1/events?city_id=warsaw")
    assert not any(e["id"] == event_id for e in public_resp.json()["events"])

    # 2. Admin inspects pending queue and publishes event
    admin_init = make_test_init_data(user_id=123456789, username="boss_admin")
    admin_headers = {"Authorization": f"tma {admin_init}"}

    pending_queue = await client.get("/api/v1/admin/events?status=pending", headers=admin_headers)
    assert pending_queue.status_code == 200
    assert any(e["id"] == event_id for e in pending_queue.json())

    pub_resp = await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=admin_headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "published"

    # 3. Now public discovery DOES show the published event
    public_resp_2 = await client.get("/api/v1/events?city_id=warsaw")
    assert any(e["id"] == event_id for e in public_resp_2.json()["events"])


def test_city_timezone_date_filter_boundaries():
    # Test Europe/Warsaw timezone calculation
    start_utc, end_utc = get_city_timezone_range("Europe/Warsaw", "today")
    assert start_utc is not None and end_utc is not None
    assert end_utc - start_utc == timedelta(days=1)
    assert start_utc.tzinfo == timezone.utc

    # Tomorrow range
    tom_start, tom_end = get_city_timezone_range("Europe/Warsaw", "tomorrow")
    assert tom_start == end_utc
    assert tom_end - tom_start == timedelta(days=1)

    # Weekend range
    w_start, w_end = get_city_timezone_range("Europe/Warsaw", "weekend")
    assert w_start is not None and w_end is not None
    assert w_end >= w_start


@pytest.mark.asyncio
async def test_spa_serving(client):
    resp = await client.get("/")
    if resp.status_code == 200:
        assert "Evently" in resp.text
        assert "<div id=\"root\"></div>" in resp.text
    else:
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Evently"


def test_database_url_normalization():
    from app.config import Settings

    # Railway standard postgres://
    s1 = Settings(DATABASE_URL="postgres://user:pass@host:5432/db")
    assert s1.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    # Standard postgresql://
    s2 = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db")
    assert s2.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    # Already async postgresql+asyncpg://
    s3 = Settings(DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db")
    assert s3.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    # SQLite remains unchanged
    s4 = Settings(DATABASE_URL="sqlite+aiosqlite:///./test.db")
    assert s4.async_database_url == "sqlite+aiosqlite:///./test.db"




