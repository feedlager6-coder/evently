import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from tests.conftest import make_test_init_data
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.event import Event, EventStatus
from app.models.view import EventView
from app.models.user import User
from app.services.notification_service import notify_organization_subscribers


@pytest.mark.asyncio
async def test_organizer_can_read_own_audience_unauthorized(client):
    """Audience endpoint requires Telegram authentication."""
    res = await client.get("/api/v1/organizer/audience")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_organizer_zero_subscribers_works(client, test_session):
    """Requirement 6: Organizations with zero subscribers return clean 0s without errors."""
    user_id = 99101
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='zero_sub_org')}"}

    # Create an organization
    create_org_res = await client.post(
        "/api/v1/organizations",
        json={
            "name": "Новый лекторий",
            "category": "Образование",
            "city_id": "makhachkala",
            "description": "Тестовый лекторий без подписчиков"
        },
        headers=auth_header
    )
    assert create_org_res.status_code == 201
    org_id = create_org_res.json()["id"]

    # Query audience
    res = await client.get("/api/v1/organizer/audience", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["total_subscribers"] == 0
    assert data["new_subscribers_7d"] == 0
    assert data["new_subscribers_30d"] == 0
    assert data["total_views"] == 0
    assert data["total_interest"] == 0
    assert data["total_attendees"] == 0
    assert data["total_unique_engaged"] == 0
    assert len(data["organizations"]) == 1
    assert data["organizations"][0]["id"] == org_id
    assert data["organizations"][0]["subscribers_count"] == 0


@pytest.mark.asyncio
async def test_subscriber_count_and_7d_30d_growth(client, test_session):
    """Requirements 3, 4, 5: Subscriber count, 7-day growth, and 30-day growth are correct."""
    owner_id = 99102
    owner_auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='club_owner')}"}

    # Create organization
    create_org_res = await client.post(
        "/api/v1/organizations",
        json={
            "name": "Джаз Клуб Времена",
            "category": "Клуб",
            "city_id": "spb"
        },
        headers=owner_auth
    )
    assert create_org_res.status_code == 201
    org_id = create_org_res.json()["id"]

    now = datetime.now(timezone.utc)

    # User 1 subscribes now (< 7 days ago)
    u1_auth = {"Authorization": f"tma {make_test_init_data(user_id=8801, username='sub_recent')}"}
    sub1_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=u1_auth)
    assert sub1_res.status_code == 200

    # User 2 subscribes 15 days ago (between 7 and 30 days)
    u2_auth = {"Authorization": f"tma {make_test_init_data(user_id=8802, username='sub_15d')}"}
    sub2_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=u2_auth)
    assert sub2_res.status_code == 200

    # User 3 subscribes 45 days ago (> 30 days)
    u3_auth = {"Authorization": f"tma {make_test_init_data(user_id=8803, username='sub_45d')}"}
    sub3_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=u3_auth)
    assert sub3_res.status_code == 200

    # Retrieve internal user PKs
    u2 = (await test_session.execute(select(User).where(User.telegram_id == 8802))).scalar_one()
    u3 = (await test_session.execute(select(User).where(User.telegram_id == 8803))).scalar_one()

    # Backdate sub2 and sub3 directly in database to test sliding time windows
    subs = (await test_session.execute(
        select(Subscription).where(Subscription.organization_id == org_id)
    )).scalars().all()

    for s in subs:
        if s.user_id == u2.id:
            s.created_at = now - timedelta(days=15)
        elif s.user_id == u3.id:
            s.created_at = now - timedelta(days=45)
    await test_session.commit()

    # Query audience
    res = await client.get("/api/v1/organizer/audience", headers=owner_auth)
    assert res.status_code == 200
    data = res.json()

    # Total subscribers should be 3
    assert data["total_subscribers"] == 3
    # 7-day growth should be 1 (only user 8801)
    assert data["new_subscribers_7d"] == 1
    # 30-day growth should be 2 (user 8801 and user 8802)
    assert data["new_subscribers_30d"] == 2
    # Breakdown on the org level
    assert data["organizations"][0]["subscribers_count"] == 3
    assert data["organizations"][0]["new_subscribers_7d"] == 1
    assert data["organizations"][0]["new_subscribers_30d"] == 2


@pytest.mark.asyncio
async def test_organizer_cannot_read_another_organization_audience(client, test_session):
    """Requirement 2: Organizer cannot access audience metrics of another organization (403 Forbidden)."""
    owner_a = 99201
    owner_b = 99202
    auth_a = {"Authorization": f"tma {make_test_init_data(user_id=owner_a, username='owner_a')}"}
    auth_b = {"Authorization": f"tma {make_test_init_data(user_id=owner_b, username='owner_b')}"}

    # Owner A creates an organization
    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Арт Пространство А", "category": "Культура", "city_id": "spb"},
        headers=auth_a
    )
    assert create_res.status_code == 201
    org_a_id = create_res.json()["id"]

    # Owner B tries to query audience filtering by Owner A's organization ID
    res = await client.get(f"/api/v1/organizer/audience?org_id={org_a_id}", headers=auth_b)
    assert res.status_code == 403
    assert "не являетесь владельцем" in res.json()["detail"]


@pytest.mark.asyncio
async def test_multiple_organizations_aggregate_correctly(client, test_session):
    """Requirement 7: Multiple organizations owned by the same user aggregate totals correctly."""
    owner_id = 99301
    owner_auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='multi_owner')}"}

    # Create Org 1
    res1 = await client.post(
        "/api/v1/organizations",
        json={"name": "Филиал Центр", "category": "Кафе", "city_id": "moscow"},
        headers=owner_auth
    )
    assert res1.status_code == 201
    org1_id = res1.json()["id"]

    # Create Org 2
    res2 = await client.post(
        "/api/v1/organizations",
        json={"name": "Филиал Север", "category": "Кафе", "city_id": "spb"},
        headers=owner_auth
    )
    assert res2.status_code == 201
    org2_id = res2.json()["id"]

    # Subscribe 2 users to Org 1
    u1_auth = {"Authorization": f"tma {make_test_init_data(user_id=7711, username='cust1')}"}
    u2_auth = {"Authorization": f"tma {make_test_init_data(user_id=7712, username='cust2')}"}
    await client.post(f"/api/v1/organizations/{org1_id}/subscribe", headers=u1_auth)
    await client.post(f"/api/v1/organizations/{org1_id}/subscribe", headers=u2_auth)

    # Subscribe 1 user to Org 2
    u3_auth = {"Authorization": f"tma {make_test_init_data(user_id=7713, username='cust3')}"}
    await client.post(f"/api/v1/organizations/{org2_id}/subscribe", headers=u3_auth)

    # Query aggregate audience
    res = await client.get("/api/v1/organizer/audience", headers=owner_auth)
    assert res.status_code == 200
    data = res.json()

    assert data["total_subscribers"] == 3
    assert len(data["organizations"]) == 2
    org_map = {o["id"]: o["subscribers_count"] for o in data["organizations"]}
    assert org_map[org1_id] == 2
    assert org_map[org2_id] == 1


@pytest.mark.asyncio
async def test_private_user_data_never_returned(client, test_session):
    """Requirement 9: Response strictly omits private user fields (telegram_id, email, phone, user_id)."""
    owner_id = 99401
    owner_auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='privacy_tester')}"}

    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Приватный Клуб", "category": "Культура", "city_id": "spb"},
        headers=owner_auth
    )
    org_id = create_res.json()["id"]

    # Subscriber with telegram_id
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=55555, username='secret_agent')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    res = await client.get("/api/v1/organizer/audience", headers=owner_auth)
    assert res.status_code == 200
    raw_text = res.text

    # Strictly check that private identifiers are not serialized
    assert "telegram_id" not in raw_text
    assert "55555" not in raw_text
    assert "secret_agent" not in raw_text
    assert "phone" not in raw_text
    assert "email" not in raw_text


@pytest.mark.asyncio
async def test_past_events_do_not_affect_public_discovery(client, test_session):
    """Requirement 8: Past events are accounted for in organizer analytics but excluded from public upcoming discovery."""
    owner_id = 99501
    owner_auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='retro_org')}"}

    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Ретро Клуб", "category": "Бар", "city_id": "spb"},
        headers=owner_auth
    )
    org_id = create_res.json()["id"]

    now = datetime.now(timezone.utc)
    # Create past event
    past_event = Event(
        title="Вчерашний Джаз",
        description="Прошедший концерт",
        category_id="music",
        city_id="spb",
        start_at=now - timedelta(days=2),
        venue_name="Ретро Бар",
        address="Невский 10",
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=owner_id,
        organization_id=org_id
    )
    test_session.add(past_event)
    await test_session.commit()
    await test_session.refresh(past_event)

    # Add a view to past event
    view = EventView(event_id=past_event.id, source="feed")
    test_session.add(view)
    await test_session.commit()

    # Public discovery query for upcoming events in SPB
    public_res = await client.get("/api/v1/events?city_id=spb")
    assert public_res.status_code == 200
    public_events = public_res.json()["events"]
    public_ids = [e["id"] for e in public_events]
    assert past_event.id not in public_ids

    # Organizer audience includes past event metrics in aggregate engagement
    audience_res = await client.get("/api/v1/organizer/audience", headers=owner_auth)
    assert audience_res.status_code == 200
    aud_data = audience_res.json()
    assert aud_data["total_views"] >= 1


@pytest.mark.asyncio
async def test_existing_notifications_behavior_unchanged(test_session):
    """Requirement 10: Existing notification dispatch to organization subscribers remains unchanged."""
    owner_id = 99601
    now = datetime.now(timezone.utc)

    # Pre-create users with telegram_id
    user1 = User(id=8881, telegram_id=8881, first_name="Sub1")
    user2 = User(id=8882, telegram_id=8882, first_name="Sub2")
    test_session.add_all([user1, user2])
    await test_session.commit()

    org = Organization(
        name="Театр Уведомлений",
        slug=f"theater-notify-{owner_id}",
        category="Театр",
        city_id="spb",
        owner_user_id=owner_id
    )
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    # Add 2 subscribers
    sub1 = Subscription(user_id=user1.id, organization_id=org.id, notifications_enabled=True)
    sub2 = Subscription(user_id=user2.id, organization_id=org.id, notifications_enabled=False)
    test_session.add_all([sub1, sub2])
    await test_session.commit()

    ev = Event(
        title="Новая премьера",
        description="Анонс спектакля",
        category_id="theatre",
        city_id="spb",
        start_at=now + timedelta(days=5),
        venue_name="Главная сцена",
        address="ул. Мира 1",
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=owner_id,
        organization_id=org.id
    )
    test_session.add(ev)
    await test_session.commit()
    await test_session.refresh(ev)

    # In dev/test mode without live bot, notify_organization_subscribers returns number of active targets
    sent = await notify_organization_subscribers(ev.id, session=test_session)
    assert sent == 1  # Only sub1 has notifications_enabled=True
