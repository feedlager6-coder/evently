import pytest
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from tests.conftest import make_test_init_data
from app.config import settings
from app.database import Base
from app.models.organization import Organization
from app.models.event import Event, EventStatus
from app.models.interest import EventInterest
from app.models.attendee import EventAttendee
from app.models.broadcast import Broadcast, BroadcastRecipient
from app.services.broadcast_service import list_organizer_broadcasts, get_broadcast_detail


def make_event_payload(org_id: str, title: str = "Test Event", days: int = 5):
    return {
        "title": title,
        "description": "Event description for testing backward compatibility.",
        "category_id": "concerts",
        "city_id": "makhachkala",
        "start_at": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
        "organization_id": org_id,
        "venue_name": "Test Venue",
    }


@pytest.fixture(autouse=True)
def setup_broadcast_tests(monkeypatch):
    """Bypasses entitlement quota and capability check for D4 backward compatibility tests."""
    from app.services.entitlement_service import EntitlementService
    async def mock_check(session, org_id, capability):
        return True, "Allowed in test", None
    async def mock_enforce(session, org_id, broadcast_type="marketing"):
        return True
    async def mock_require(session, org_id, capability):
        return True
    monkeypatch.setattr(EntitlementService, "check_capability", mock_check)
    monkeypatch.setattr(EntitlementService, "enforce_broadcast_capacity", mock_enforce)
    monkeypatch.setattr(EntitlementService, "require_entitlement", mock_require)


@pytest.mark.asyncio
async def test_schema_migration_preserves_d40_legacy_broadcasts(tmp_path):
    """
    Verifies that unmigrated D4.0 production databases (lacking D4.1 attribution columns)
    are safely migrated without data loss, and legacy broadcasts remain readable and listable.
    """
    db_path = str(tmp_path / "legacy_test.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tables exactly as they existed in D4.0 (without attribution_token and without opened_at)
    c.executescript("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        username VARCHAR(255),
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255),
        avatar_url TEXT,
        default_city_id TEXT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL
    );
    CREATE TABLE cities (
        id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        region VARCHAR(100) NOT NULL,
        country VARCHAR(100) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        latitude FLOAT,
        longitude FLOAT
    );
    CREATE TABLE organizations (
        id VARCHAR(36) PRIMARY KEY,
        owner_user_id INTEGER NOT NULL REFERENCES users(id),
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) UNIQUE NOT NULL,
        description TEXT,
        category VARCHAR(50) NOT NULL,
        city_id VARCHAR(50) REFERENCES cities(id),
        address VARCHAR(255),
        latitude FLOAT,
        longitude FLOAT,
        avatar_url VARCHAR(1024),
        website VARCHAR(1024),
        social_link VARCHAR(1024),
        status VARCHAR(20) NOT NULL DEFAULT 'active',
        is_verified BOOLEAN NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL
    );
    CREATE TABLE subscriptions (
        id VARCHAR(36) PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
        notifications_enabled BOOLEAN NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL
    );
    CREATE TABLE events (
        id VARCHAR(36) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        cover_image_url VARCHAR(1024),
        category_id VARCHAR(50) NOT NULL,
        city_id VARCHAR(50) NOT NULL,
        start_at TIMESTAMP NOT NULL,
        venue_name VARCHAR(255) NOT NULL,
        address VARCHAR(255) NOT NULL,
        latitude FLOAT,
        longitude FLOAT,
        price_amount FLOAT,
        price_currency VARCHAR(10),
        status VARCHAR(20) NOT NULL DEFAULT 'published',
        organizer_user_id INTEGER NOT NULL REFERENCES users(id),
        organization_id VARCHAR(36) REFERENCES organizations(id),
        rejection_reason TEXT,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL
    );
    CREATE TABLE broadcasts (
        id VARCHAR(36) PRIMARY KEY,
        organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
        created_by_user_id INTEGER REFERENCES users(id),
        event_id VARCHAR(36) REFERENCES events(id),
        target_type VARCHAR(50) NOT NULL,
        broadcast_type VARCHAR(30) NOT NULL,
        template_key VARCHAR(50) NOT NULL,
        custom_text VARCHAR(300),
        status VARCHAR(30) NOT NULL,
        total_recipients INTEGER NOT NULL,
        sent_count INTEGER NOT NULL,
        delivered_count INTEGER NOT NULL,
        failed_count INTEGER NOT NULL,
        blocked_count INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL,
        started_at TIMESTAMP,
        completed_at TIMESTAMP
    );
    CREATE TABLE broadcast_recipients (
        id VARCHAR(36) PRIMARY KEY,
        broadcast_id VARCHAR(36) NOT NULL REFERENCES broadcasts(id),
        user_id INTEGER NOT NULL REFERENCES users(id),
        status VARCHAR(20) NOT NULL,
        telegram_message_id BIGINT,
        error_code VARCHAR(50),
        error_message TEXT,
        sent_at TIMESTAMP,
        clicked_at TIMESTAMP
    );

    -- Insert existing D4.0 production data: user, org, subscriber, 2 existing broadcasts
    INSERT INTO users VALUES (1, 1001, 'org_owner', 'Organizer', NULL, NULL, NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO users VALUES (2, 1002, 'subscriber', 'Fan', NULL, NULL, NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO organizations VALUES ('org-1', 1, 'Historical Org', 'hist-org', 'Desc', 'Кафе', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'active', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO subscriptions VALUES ('sub-1', 2, 'org-1', 1, CURRENT_TIMESTAMP);

    INSERT INTO broadcasts VALUES ('bcast-hist-1', 'org-1', 1, NULL, 'organization_subscribers', 'marketing', 'custom_update', 'Hist 1', 'completed', 1, 1, 1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    INSERT INTO broadcasts VALUES ('bcast-hist-2', 'org-1', 1, NULL, 'organization_subscribers', 'marketing', 'custom_update', 'Hist 2', 'completed', 1, 1, 1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

    INSERT INTO broadcast_recipients VALUES ('rec-1', 'bcast-hist-1', 2, 'sent', 9001, NULL, NULL, CURRENT_TIMESTAMP, NULL);
    INSERT INTO broadcast_recipients VALUES ('rec-2', 'bcast-hist-2', 2, 'sent', 9002, NULL, NULL, CURRENT_TIMESTAMP, NULL);
    """)
    conn.commit()
    conn.close()

    # Now create an engine pointing to this db and run init_db logic
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    # Execute migrations exactly as done in app.database.init_db
    migrations = [
        ("events", "allow_event_contact", "BOOLEAN DEFAULT FALSE", "BOOLEAN DEFAULT 0"),
        ("events", "source_type", "VARCHAR(30) DEFAULT 'user'", "VARCHAR(30) DEFAULT 'user'"),
        ("events", "source_name", "VARCHAR(100)", "VARCHAR(100)"),
        ("events", "external_id", "VARCHAR(255)", "VARCHAR(255)"),
        ("events", "source_url", "VARCHAR(1024)", "VARCHAR(1024)"),
        ("events", "last_synced_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
        ("broadcasts", "attribution_token", "VARCHAR(32)", "VARCHAR(32)"),
        ("broadcast_recipients", "opened_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
        ("broadcast_recipients", "attributed_interest_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
        ("broadcast_recipients", "attributed_rsvp_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
    ]
    async with engine.begin() as conn_async:
        for table, col, _, sqlite_type in migrations:
            res = await conn_async.execute(text(f"PRAGMA table_info({table});"))
            existing_cols = [row[1] for row in res.fetchall()]
            if existing_cols and col not in existing_cols:
                await conn_async.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sqlite_type};"))

        indexes = [
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_broadcasts_attribution_token ON broadcasts (attribution_token);",
            "CREATE INDEX IF NOT EXISTS idx_broadcast_recipients_attr ON broadcast_recipients (user_id, broadcast_id, opened_at);",
        ]
        for idx_sql in indexes:
            await conn_async.execute(text(idx_sql))

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # Verify 1: Both legacy broadcasts exist and are returned by list_organizer_broadcasts
        items = await list_organizer_broadcasts(session, organizer_user_id=1)
        assert len(items) == 2
        assert {item.id for item in items} == {"bcast-hist-1", "bcast-hist-2"}
        for item in items:
            assert item.status == "completed"
            assert item.delivered_count == 1
            assert item.open_rate == 0.0
            assert item.opened_count == 0

        # Verify 2: get_broadcast_detail succeeds for legacy broadcast with None token
        detail = await get_broadcast_detail(session, organizer_user_id=1, broadcast_id="bcast-hist-1")
        assert detail.id == "bcast-hist-1"
        assert detail.attribution_token is None
        assert "startapp=org_org-1" in detail.button_url

    await engine.dispose()


@pytest.mark.asyncio
async def test_legacy_broadcast_listing_and_detail_with_null_tokens(client, test_session):
    """
    Ensures that existing broadcasts created before D4.1 (where attribution_token is NULL)
    remain completely visible in list and detail endpoints via the API.
    """
    owner_id = 9201
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_legacy')}"}

    # 1. Create Org
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Legacy Venue", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    # 2. Add an event
    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Old Event", 2),
        headers=auth_owner,
    )
    assert res_ev.status_code == 201
    event_id = res_ev.json()["id"]

    # Approve event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # 3. Insert a legacy Broadcast directly into DB with attribution_token=None
    legacy_bcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_id,
        event_id=event_id,
        target_type="organization_subscribers",
        broadcast_type="marketing",
        template_key="event_announcement",
        custom_text="Legacy message before D4.1",
        status="completed",
        attribution_token=None,  # Old broadcast without token
        total_recipients=5,
        sent_count=5,
        delivered_count=5,
        failed_count=0,
        blocked_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
        started_at=datetime.now(timezone.utc) - timedelta(days=3),
        completed_at=datetime.now(timezone.utc) - timedelta(days=3),
    )
    test_session.add(legacy_bcast)
    await test_session.commit()

    # Explicitly clear attribution_token to simulate legacy pre-D4.1 row
    await test_session.execute(
        text("UPDATE broadcasts SET attribution_token = NULL WHERE id = :bid"),
        {"bid": legacy_bcast.id}
    )
    await test_session.commit()
    test_session.expire_all()

    # 4. Query list via API
    res_list = await client.get("/api/v1/organizer/broadcasts", headers=auth_owner)
    assert res_list.status_code == 200
    items = res_list.json()
    matched = [b for b in items if b["id"] == legacy_bcast.id]
    assert len(matched) == 1
    item = matched[0]
    assert item["id"] == legacy_bcast.id
    assert item["open_rate"] == 0.0
    assert item["opened_count"] == 0
    assert item["interest_count"] == 0
    assert item["rsvp_count"] == 0

    # 5. Query detail via API
    res_detail = await client.get(f"/api/v1/organizer/broadcasts/{legacy_bcast.id}", headers=auth_owner)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == legacy_bcast.id
    assert detail["attribution_token"] is None
    assert f"event_{event_id}" in detail["button_url"]
    # Token suffix should NOT be in button_url since token is None
    assert "_b_" not in detail["button_url"]


@pytest.mark.asyncio
async def test_all_target_and_template_combinations_create_successfully(client, test_session, monkeypatch):
    monkeypatch.setattr(settings, "FREE_BROADCASTS_PER_MONTH", 10)
    """
    Verifies that all 4 supported combinations can be created successfully:
    1. organization_subscribers + event_announcement
    2. organization_subscribers + custom_update (no event_id)
    3. event_interest + event_announcement
    4. event_interest + event_update
    """
    owner_id = 9301
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_combos')}"}

    # Create Org
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Multi-Combo Org", "category": "Концертная площадка", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    # Create Event
    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Festival Day", 10),
        headers=auth_owner,
    )
    assert res_ev.status_code == 201
    event_id = res_ev.json()["id"]

    # Publish event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Subscriber 1 for organization
    sub1_id = 9311
    auth_sub1 = {"Authorization": f"tma {make_test_init_data(user_id=sub1_id, username='sub_combo1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_sub1)

    # Interested user 2 for event
    int2_id = 9312
    auth_int2 = {"Authorization": f"tma {make_test_init_data(user_id=int2_id, username='int_combo2')}"}
    await client.post(f"/api/v1/events/{event_id}/interest", headers=auth_int2)

    # Combo 1: organization_subscribers + event_announcement
    res1 = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
            "custom_text": "Combo 1 Announcement",
        },
        headers=auth_owner,
    )
    assert res1.status_code == 200, res1.text
    bcast1 = res1.json()
    assert bcast1["attribution_token"] is not None
    assert bcast1["total_recipients"] >= 1

    # Combo 2: organization_subscribers + custom_update (no event_id)
    # Add another subscriber who hasn't received anything
    sub2_id = 9313
    auth_sub2 = {"Authorization": f"tma {make_test_init_data(user_id=sub2_id, username='sub_combo2')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_sub2)

    res2 = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Combo 2 Org News",
        },
        headers=auth_owner,
    )
    assert res2.status_code == 200, res2.text
    bcast2 = res2.json()
    assert bcast2["event_id"] is None
    assert bcast2["attribution_token"] is not None

    # Combo 3: event_interest + event_announcement
    res3 = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "event_interest",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
            "custom_text": "Combo 3 Announcement to Interested",
        },
        headers=auth_owner,
    )
    assert res3.status_code == 200, res3.text
    bcast3 = res3.json()
    assert bcast3["event_id"] == event_id

    # Anti-abuse: Manual transactional broadcast creation is rejected with 400
    res4 = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "event_interest",
            "broadcast_type": "transactional",
            "template_key": "event_update",
            "event_id": event_id,
            "custom_text": "Combo 4 Time Change",
        },
        headers=auth_owner,
    )
    assert res4.status_code == 400

    # Verify marketing broadcasts are returned in list
    res_list = await client.get("/api/v1/organizer/broadcasts", headers=auth_owner)
    assert res_list.status_code == 200
    returned_ids = {b["id"] for b in res_list.json()}
    assert {bcast1["id"], bcast2["id"], bcast3["id"]}.issubset(returned_ids)


@pytest.mark.asyncio
async def test_d41_attribution_flow_for_new_broadcasts(client, test_session):
    """
    Verifies that D4.1 attribution functionality remains fully operational:
    broadcast -> view -> interest -> RSVP.
    """
    owner_id = 9401
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_attr_flow')}"}

    # 1. Org & Event
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Attribution Venue Flow", "category": "Спорт", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Basketball Finals", 7),
        headers=auth_owner,
    )
    assert res_ev.status_code == 201
    event_id = res_ev.json()["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # 2. Subscribe User
    fan_id = 9411
    auth_fan = {"Authorization": f"tma {make_test_init_data(user_id=fan_id, username='fan_attr')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_fan)

    # 3. Create Broadcast
    res_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
        },
        headers=auth_owner,
    )
    assert res_bcast.status_code == 200
    bcast = res_bcast.json()
    token = bcast["attribution_token"]
    assert token is not None

    # 4. View event with broadcast attribution token
    res_view = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "telegram_broadcast", "broadcast_token": token},
        headers=auth_fan,
    )
    assert res_view.status_code == 200

    # 5. Fan adds interest
    res_int = await client.post(f"/api/v1/events/{event_id}/interest", headers=auth_fan)
    assert res_int.status_code == 200

    # 6. Fan RSVPs
    res_rsvp = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=auth_fan)
    assert res_rsvp.status_code == 200

    # 7. Check broadcast detail analytics
    res_detail = await client.get(f"/api/v1/organizer/broadcasts/{bcast['id']}", headers=auth_owner)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["opened_count"] == 1
    assert detail["interest_count"] == 1
    assert detail["rsvp_count"] == 1
    assert detail["open_rate"] == 100.0
    assert detail["interest_conversion"] == 100.0
    assert detail["rsvp_conversion"] == 100.0


@pytest.mark.asyncio
async def test_legacy_broadcast_when_event_deleted(client, test_session):
    """
    Ensures that get_broadcast_detail does not crash if a historical broadcast's
    referenced event has been removed from the database.
    """
    owner_id = 9501
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_deleted_ev')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Org With Deleted Event", "category": "Другое", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    # Insert broadcast where event_id is None or nonexistent
    bcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_id,
        event_id=None,
        target_type="organization_subscribers",
        broadcast_type="marketing",
        template_key="event_announcement",
        custom_text="Event was removed",
        status="completed",
        attribution_token=None,
        total_recipients=1,
        sent_count=1,
        delivered_count=1,
        created_at=datetime.now(timezone.utc),
    )
    test_session.add(bcast)
    await test_session.commit()

    # Detail query should gracefully handle missing event without 400 or 500
    res_detail = await client.get(f"/api/v1/organizer/broadcasts/{bcast.id}", headers=auth_owner)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == bcast.id
    assert detail["custom_text"] == "Event was removed"
