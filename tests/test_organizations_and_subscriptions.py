import pytest
from unittest.mock import AsyncMock, patch
from tests.conftest import make_test_init_data


@pytest.mark.asyncio
async def test_create_organization_flow(client):
    """Verifies that an authenticated user can create an organization."""
    user_a_init = make_test_init_data(user_id=1001, username="user_a")
    headers_a = {"Authorization": f"tma {user_a_init}"}

    payload = {
        "name": "Coffee Lab",
        "category": "Кафе",
        "description": "Лучший спешелти кофе в Махачкале",
        "city_id": "makhachkala",
        "address": "ул. Ленина, 15",
        "website": "https://coffeelab.example.com",
        "social_link": "https://t.me/coffeelab"
    }

    res = await client.post("/api/v1/organizations", json=payload, headers=headers_a)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Coffee Lab"
    assert "coffee-lab" in data["slug"]
    assert data["category"] == "Кафе"
    assert data["city_id"] == "makhachkala"
    assert data["followers_count"] == 0
    assert data["is_owner"] is True
    assert data["status"] == "active"
    org_id = data["id"]

    # Public fetch by ID
    pub_res = await client.get(f"/api/v1/organizations/{org_id}")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()
    assert pub_data["name"] == "Coffee Lab"
    assert pub_data["followers_count"] == 0
    assert pub_data["is_subscribed"] is False

    # Public fetch by slug
    slug_res = await client.get(f"/api/v1/organizations/{data['slug']}")
    assert slug_res.status_code == 200
    assert slug_res.json()["id"] == org_id


@pytest.mark.asyncio
async def test_create_organization_unauthenticated_fails(client):
    """Anonymous creation must return 401 Unauthorized."""
    payload = {
        "name": "Unauthorized Place",
        "category": "Бар"
    }
    res = await client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_organization_ownership_authorization(client):
    """Owner can update organization; non-owners are strictly rejected with 403."""
    user_a_init = make_test_init_data(user_id=1002, username="owner_a")
    headers_a = {"Authorization": f"tma {user_a_init}"}

    # 1. Create org by user A
    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "LOFT 05", "category": "Клуб", "description": "Old description"},
        headers=headers_a
    )
    assert create_res.status_code == 201
    org_id = create_res.json()["id"]

    # 2. Owner updates org
    update_res = await client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"description": "New updated description", "address": "ул. Гаджиева, 5"},
        headers=headers_a
    )
    assert update_res.status_code == 200
    assert update_res.json()["description"] == "New updated description"
    assert update_res.json()["address"] == "ул. Гаджиева, 5"

    # 3. User B attempts to update User A's organization -> 403 Forbidden
    user_b_init = make_test_init_data(user_id=1003, username="intruder_b")
    headers_b = {"Authorization": f"tma {user_b_init}"}

    forbidden_res = await client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"description": "Hacked description"},
        headers=headers_b
    )
    assert forbidden_res.status_code == 403
    assert "не можете редактировать чужую организацию" in forbidden_res.json()["detail"]


@pytest.mark.asyncio
async def test_list_my_organizations(client):
    """GET /api/v1/organizations/me returns only organizations owned by the caller."""
    user_a_init = make_test_init_data(user_id=1004, username="user_a_my")
    headers_a = {"Authorization": f"tma {user_a_init}"}
    user_b_init = make_test_init_data(user_id=1005, username="user_b_my")
    headers_b = {"Authorization": f"tma {user_b_init}"}

    # User A creates two organizations
    await client.post("/api/v1/organizations", json={"name": "Org 1", "category": "Кафе"}, headers=headers_a)
    await client.post("/api/v1/organizations", json={"name": "Org 2", "category": "Спорт"}, headers=headers_a)

    # User A sees 2 organizations
    my_a = await client.get("/api/v1/organizations/me", headers=headers_a)
    assert my_a.status_code == 200
    assert len(my_a.json()) == 2

    # User B sees 0 organizations
    my_b = await client.get("/api/v1/organizations/me", headers=headers_b)
    assert my_b.status_code == 200
    assert len(my_b.json()) == 0


@pytest.mark.asyncio
async def test_subscriptions_idempotent_flow(client):
    """Verifies subscribe, duplicate subscribe, unsubscribe, and subscriptions list."""
    owner_init = make_test_init_data(user_id=1006, username="owner_org")
    headers_owner = {"Authorization": f"tma {owner_init}"}
    sub_init = make_test_init_data(user_id=1007, username="subscriber_user")
    headers_sub = {"Authorization": f"tma {sub_init}"}

    # 1. Create Organization
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Comedy Club Makhachkala", "category": "Театр"},
        headers=headers_owner
    )
    org_id = org_res.json()["id"]

    # 2. Subscribe
    sub_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=headers_sub)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["is_subscribed"] is True
    assert sub_data["followers_count"] == 1

    # 3. Duplicate subscribe (idempotent)
    dup_sub_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=headers_sub)
    assert dup_sub_res.status_code == 200
    assert dup_sub_res.json()["is_subscribed"] is True
    assert dup_sub_res.json()["followers_count"] == 1

    # 4. Check org profile reflects subscriber status
    org_check = await client.get(f"/api/v1/organizations/{org_id}", headers=headers_sub)
    assert org_check.status_code == 200
    assert org_check.json()["is_subscribed"] is True
    assert org_check.json()["followers_count"] == 1

    # 5. List user subscriptions via /api/v1/users/me/subscriptions
    my_subs_res = await client.get("/api/v1/users/me/subscriptions", headers=headers_sub)
    assert my_subs_res.status_code == 200
    subs_list = my_subs_res.json()
    assert len(subs_list) == 1
    assert subs_list[0]["organization"]["id"] == org_id
    assert subs_list[0]["organization"]["followers_count"] == 1

    # 6. Unsubscribe
    unsub_res = await client.delete(f"/api/v1/organizations/{org_id}/subscribe", headers=headers_sub)
    assert unsub_res.status_code == 200
    assert unsub_res.json()["is_subscribed"] is False
    assert unsub_res.json()["followers_count"] == 0

    # 7. Duplicate unsubscribe (safe & idempotent)
    dup_unsub_res = await client.delete(f"/api/v1/organizations/{org_id}/subscribe", headers=headers_sub)
    assert dup_unsub_res.status_code == 200
    assert dup_unsub_res.json()["is_subscribed"] is False
    assert dup_unsub_res.json()["followers_count"] == 0


@pytest.mark.asyncio
async def test_create_event_with_organization_and_authorization(client):
    """Verifies that an owner can create an event under their organization, but not under someone else's."""
    user_a_init = make_test_init_data(user_id=1008, username="user_a_org")
    headers_a = {"Authorization": f"tma {user_a_init}"}
    user_b_init = make_test_init_data(user_id=1009, username="user_b_org")
    headers_b = {"Authorization": f"tma {user_b_init}"}

    # 1. User A creates organization
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Jazz Club", "category": "Концертная площадка"},
        headers=headers_a
    )
    org_id = org_res.json()["id"]

    # 2. User A creates event with organization_id
    event_payload_a = {
        "title": "Evening of Live Jazz",
        "description": "Wonderful evening with acoustic jazz performances.",
        "category_id": "concerts",
        "city_id": "makhachkala",
        "start_at": "2026-10-15T19:00:00Z",
        "venue_name": "Jazz Club Stage",
        "address": "ул. Пушкина, 10",
        "price_amount": 500,
        "price_currency": "RUB",
        "organization_id": org_id
    }
    create_ev_res = await client.post("/api/v1/events", json=event_payload_a, headers=headers_a)
    assert create_ev_res.status_code == 201
    ev_data = create_ev_res.json()
    assert ev_data["organization_id"] == org_id
    assert ev_data["organization_name"] == "Jazz Club"
    assert ev_data["status"] == "pending"

    # 3. User B attempts to create event with User A's organization_id -> 403 Forbidden
    event_payload_b = {
        **event_payload_a,
        "title": "Impostor Event"
    }
    forbidden_ev_res = await client.post("/api/v1/events", json=event_payload_b, headers=headers_b)
    assert forbidden_ev_res.status_code == 403
    assert "не можете создавать мероприятия от имени чужой организации" in forbidden_ev_res.json()["detail"]


@pytest.mark.asyncio
async def test_organization_events_endpoint_and_publishing_notification(client):
    """
    Verifies that:
    1. Organization events endpoint returns pending events to owner, but only published to public.
    2. Publishing the event triggers notification to subscribers via background task.
    """
    admin_init = make_test_init_data(user_id=123456789, username="admin_user")
    headers_admin = {"Authorization": f"tma {admin_init}"}

    owner_init = make_test_init_data(user_id=1010, username="org_owner")
    headers_owner = {"Authorization": f"tma {owner_init}"}

    sub_init = make_test_init_data(user_id=1011, username="subscriber")
    headers_sub = {"Authorization": f"tma {sub_init}"}

    # 1. Create organization
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Art Space 05", "category": "Культура"},
        headers=headers_owner
    )
    org_id = org_res.json()["id"]

    # 2. User subscribes to organization
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=headers_sub)

    # 3. Create event under organization (enters pending)
    ev_payload = {
        "title": "Modern Art Exhibition",
        "description": "Contemporary artists exhibition with guided tour.",
        "category_id": "exhibitions",
        "city_id": "makhachkala",
        "start_at": "2026-10-20T18:00:00Z",
        "venue_name": "Art Space Hall",
        "address": "пр. Расула Гамзатова, 45",
        "organization_id": org_id
    }
    ev_create_res = await client.post("/api/v1/events", json=ev_payload, headers=headers_owner)
    assert ev_create_res.status_code == 201
    event_id = ev_create_res.json()["id"]

    # 4. Public events for org should be empty while event is pending
    public_org_events = await client.get(f"/api/v1/organizations/{org_id}/events")
    assert public_org_events.status_code == 200
    assert len(public_org_events.json()) == 0

    # 5. Owner can see the pending event in org events
    owner_org_events = await client.get(f"/api/v1/organizations/{org_id}/events", headers=headers_owner)
    assert owner_org_events.status_code == 200
    assert len(owner_org_events.json()) == 1
    assert owner_org_events.json()[0]["id"] == event_id

    # 6. Admin publishes the event (triggers background notification task)
    with patch("app.services.notification_service.notify_organization_subscribers", new_callable=AsyncMock) as mock_notify:
        pub_res = await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=headers_admin)
        assert pub_res.status_code == 200
        assert pub_res.json()["status"] == "published"
        # Verify notification task was enqueued
        mock_notify.assert_called_once_with(event_id)

    # 7. Now public org events returns the published event
    public_org_events_after = await client.get(f"/api/v1/organizations/{org_id}/events")
    assert public_org_events_after.status_code == 200
    assert len(public_org_events_after.json()) == 1
    assert public_org_events_after.json()[0]["id"] == event_id


@pytest.mark.asyncio
async def test_create_event_optional_address_and_fallback(client):
    """
    Verifies that address is optional when creating an event from an organization,
    and falls back to organization address or venue_name.
    """
    owner_init = make_test_init_data(user_id=1020, username="org_address_test")
    headers_owner = {"Authorization": f"tma {owner_init}"}

    # 1. Create Organization with an address and coordinates
    org_res = await client.post(
        "/api/v1/organizations",
        json={
            "name": "Loft Space 05",
            "category": "Культура",
            "address": "ул. Коркмасова, 15",
            "latitude": 42.98,
            "longitude": 47.50
        },
        headers=headers_owner
    )
    assert org_res.status_code == 201
    org_id = org_res.json()["id"]

    # 2. Create Event under org WITHOUT address field
    ev_payload_org = {
        "title": "Acoustic Night",
        "description": "Live acoustic guitar performance in cozy loft atmosphere.",
        "category_id": "concerts",
        "city_id": "makhachkala",
        "start_at": "2026-11-01T19:00:00Z",
        "venue_name": "Loft Space 05 Main Hall",
        "organization_id": org_id
        # address is deliberately omitted
    }
    res_org = await client.post("/api/v1/events", json=ev_payload_org, headers=headers_owner)
    assert res_org.status_code == 201, f"Expected 201, got {res_org.status_code}: {res_org.text}"
    ev_data = res_org.json()
    assert ev_data["organization_id"] == org_id
    assert ev_data["address"] == "ул. Коркмасова, 15"
    assert ev_data["latitude"] == 42.98

    # 3. Create Event without org and WITHOUT address field (falls back to venue_name)
    ev_payload_personal = {
        "title": "Street Workout Meetup",
        "description": "Friendly outdoor workout and masterclass on bar pull-ups.",
        "category_id": "sports",
        "city_id": "makhachkala",
        "start_at": "2026-11-02T10:00:00Z",
        "venue_name": "Central Beach Workout Area"
        # address is deliberately omitted
    }
    res_pers = await client.post("/api/v1/events", json=ev_payload_personal, headers=headers_owner)
    assert res_pers.status_code == 201, f"Expected 201, got {res_pers.status_code}: {res_pers.text}"
    assert res_pers.json()["address"] == "Central Beach Workout Area"
