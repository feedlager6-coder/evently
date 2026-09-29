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
    assert len(cities) >= 15
    city_ids = [c["id"] for c in cities]
    assert "makhachkala" in city_ids
    assert "moscow" in city_ids
    assert "spb" in city_ids
    assert "kazan" in city_ids
    assert "sochi" in city_ids

    # Verify coordinates are present
    mkh = next(c for c in cities if c["id"] == "makhachkala")
    assert mkh["latitude"] is not None
    assert mkh["longitude"] is not None

    # Categories
    cat_resp = await client.get("/api/v1/categories")
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    assert len(categories) == 7
    slugs = [c["slug"] for c in categories]
    assert "concerts" in slugs
    assert "sports" in slugs


@pytest.mark.asyncio
async def test_cities_search_and_nearest(client):
    # Search by Russian name query
    q_resp = await client.get("/api/v1/cities?q=махачкала")
    assert q_resp.status_code == 200
    results = q_resp.json()
    assert len(results) >= 1
    assert results[0]["id"] == "makhachkala"

    # Nearest city lookup near SPb (59.93, 30.31)
    near_resp = await client.get("/api/v1/cities/nearest?latitude=59.9386&longitude=30.3141")
    assert near_resp.status_code == 200
    near_city = near_resp.json()
    assert near_city["id"] == "spb"


@pytest.mark.asyncio
async def test_location_suggestions(client):
    resp = await client.get("/api/v1/locations/suggest?q=Пушкина&city_id=makhachkala")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "display_name" in data[0]
    assert "latitude" in data[0]
    assert "longitude" in data[0]


@pytest.mark.asyncio
async def test_cover_image_upload_validation(client):
    # 1. Valid JPEG
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 100
    files = {"file": ("test.jpg", jpeg_bytes, "image/jpeg")}
    resp = await client.post("/api/v1/events/upload-cover", files=files)
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("/uploads/covers/")

    # 2. Invalid fake image (text/plain disguised as jpeg)
    fake_files = {"file": ("fake.jpg", b"hello not an image", "image/jpeg")}
    fake_resp = await client.post("/api/v1/events/upload-cover", files=fake_files)
    assert fake_resp.status_code == 400


@pytest.mark.asyncio
async def test_user_me_endpoint(client):
    # Non-admin user
    regular_init = make_test_init_data(user_id=888999, username="regular_user")
    resp_reg = await client.get("/api/v1/users/me", headers={"Authorization": f"tma {regular_init}"})
    assert resp_reg.status_code == 200
    user_reg = resp_reg.json()
    assert user_reg["telegram_id"] == 888999
    assert user_reg["is_admin"] is False

    # Admin user (ID 123456789 from test settings)
    admin_init = make_test_init_data(user_id=123456789, username="super_admin")
    resp_admin = await client.get("/api/v1/users/me", headers={"Authorization": f"tma {admin_init}"})
    assert resp_admin.status_code == 200
    user_admin = resp_admin.json()
    assert user_admin["telegram_id"] == 123456789
    assert user_admin["is_admin"] is True


@pytest.mark.asyncio
async def test_events_discovery_filtering(client):
    # 1. SPb events
    spb_resp = await client.get("/api/v1/events?city_id=spb")
    assert spb_resp.status_code == 200
    data = spb_resp.json()
    assert data["city_id"] == "spb"
    assert len(data["events"]) >= 10

    # 2. SPb concerts filter
    concerts_resp = await client.get("/api/v1/events?city_id=spb&category_id=concerts")
    assert concerts_resp.status_code == 200
    c_data = concerts_resp.json()
    assert len(c_data["events"]) >= 1
    for ev in c_data["events"]:
        assert ev["category_id"] == "concerts"


@pytest.mark.asyncio
async def test_event_details_and_rsvp_api_flow(client):
    # Discover first SPb event
    spb_resp = await client.get("/api/v1/events?city_id=spb")
    event_id = spb_resp.json()["events"][0]["id"]

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
    # 1. Organizer submits event with coordinates
    org_init = make_test_init_data(user_id=111222333, username="cool_organizer")
    org_headers = {"Authorization": f"tma {org_init}"}

    now = datetime.now(timezone.utc)
    event_payload = {
        "title": "Makhachkala Sunset Music Fest",
        "description": "Live ethno and electronic beats by the Caspian coast.",
        "cover_image_url": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30",
        "category_id": "parties",
        "city_id": "makhachkala",
        "start_at": (now + timedelta(days=5)).isoformat(),
        "venue_name": "Каспийский берег",
        "address": "ул. Приморская, 10",
        "latitude": 42.9831,
        "longitude": 47.5046,
        "price_amount": 500.0,
        "price_currency": "RUB"
    }

    create_resp = await client.post("/api/v1/events", json=event_payload, headers=org_headers)
    assert create_resp.status_code == 201
    created_event = create_resp.json()
    event_id = created_event["id"]
    assert created_event["status"] == "pending"
    assert created_event["latitude"] == 42.9831
    assert created_event["longitude"] == 47.5046

    # Organizer sees it in /organizer/events
    my_events_resp = await client.get("/api/v1/organizer/events", headers=org_headers)
    assert my_events_resp.status_code == 200
    assert any(e["id"] == event_id for e in my_events_resp.json())

    # Regular public discovery does NOT show pending event
    public_resp = await client.get("/api/v1/events?city_id=makhachkala")
    assert not any(e["id"] == event_id for e in public_resp.json()["events"])

    # 2. Admin inspects pending queue and publishes event
    admin_init = make_test_init_data(user_id=123456789, username="boss_admin")
    admin_headers = {"Authorization": f"tma {admin_init}"}

    # Verify query parameter alias support (?status=pending vs ?status_filter=pending)
    pending_queue = await client.get("/api/v1/admin/events?status=pending", headers=admin_headers)
    assert pending_queue.status_code == 200
    assert any(e["id"] == event_id for e in pending_queue.json())

    pub_resp = await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=admin_headers)
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "published"

    # 3. Now public discovery DOES show the published event
    public_resp_2 = await client.get("/api/v1/events?city_id=makhachkala")
    assert any(e["id"] == event_id for e in public_resp_2.json()["events"])


def test_city_timezone_date_filter_boundaries():
    # Test Europe/Moscow timezone calculation
    start_utc, end_utc = get_city_timezone_range("Europe/Moscow", "today")
    assert start_utc is not None and end_utc is not None
    assert end_utc - start_utc == timedelta(days=1)
    assert start_utc.tzinfo == timezone.utc

    # Tomorrow range
    tom_start, tom_end = get_city_timezone_range("Europe/Moscow", "tomorrow")
    assert tom_start == end_utc
    assert tom_end - tom_start == timedelta(days=1)

    # Weekend range
    w_start, w_end = get_city_timezone_range("Europe/Moscow", "weekend")
    assert w_start is not None and w_end is not None
    assert w_end >= w_start


@pytest.mark.asyncio
async def test_spa_serving(client):
    resp = await client.get("/")
    if resp.status_code == 200:
        assert "Ivently" in resp.text or "Evently" in resp.text
        assert "<div id=\"root\"></div>" in resp.text
    else:
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Ivently"


@pytest.mark.asyncio
async def test_app_meta_endpoint(client):
    resp = await client.get("/api/v1/meta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["app_name"] == "Ivently"
    assert data["bot_username"] == "Ivently_bot"
    assert "https://t.me/Ivently_bot/app" in data["mini_app_url"]



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
