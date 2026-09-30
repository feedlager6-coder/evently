import pytest
from sqlalchemy import select
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.view import EventView
from tests.conftest import make_test_init_data


@pytest.mark.asyncio
async def test_owner_can_delete_event(client):
    """
    Organizer who created the event can safely delete it.
    After deletion, the endpoint returns 200, public get returns 404,
    and the event is excluded from organizer events.
    """
    owner_init = make_test_init_data(user_id=7101, username="org_owner_7101")
    owner_headers = {"Authorization": f"tma {owner_init}"}

    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Indie Festival 2026",
            "description": "Annual indie music festival in Makhachkala.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": "2026-11-25T18:00:00Z",
            "venue_name": "Summer Amphitheatre",
            "address": "ул. Ленина, 1"
        },
        headers=owner_headers
    )
    assert create_res.status_code == 201
    event_id = create_res.json()["id"]

    # Verify event appears in organizer list
    org_events = await client.get("/api/v1/organizer/events", headers=owner_headers)
    assert any(e["id"] == event_id for e in org_events.json())

    # Owner deletes the event
    del_res = await client.delete(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["ok"] is True
    assert "успешно удалено" in del_data["message"]

    # GET /events/{id} returns 404
    get_res = await client.get(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert get_res.status_code == 404

    # Excluded from organizer list
    org_events_after = await client.get("/api/v1/organizer/events", headers=owner_headers)
    assert not any(e["id"] == event_id for e in org_events_after.json())


@pytest.mark.asyncio
async def test_non_owner_cannot_delete_event(client):
    """
    Non-owner attempting to delete an event receives strict 403 Forbidden.
    """
    owner_init = make_test_init_data(user_id=7102, username="owner_7102")
    intruder_init = make_test_init_data(user_id=7103, username="intruder_7103")
    owner_headers = {"Authorization": f"tma {owner_init}"}
    intruder_headers = {"Authorization": f"tma {intruder_init}"}

    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Private Party",
            "description": "Exclusive event.",
            "category_id": "parties",
            "city_id": "makhachkala",
            "start_at": "2026-11-26T20:00:00Z",
            "venue_name": "Sky Bar",
            "address": "ул. Гагарина, 5"
        },
        headers=owner_headers
    )
    assert create_res.status_code == 201
    event_id = create_res.json()["id"]

    # Intruder tries to delete
    del_res = await client.delete(f"/api/v1/events/{event_id}", headers=intruder_headers)
    assert del_res.status_code == 403

    # Event remains intact
    get_res = await client.get(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert get_res.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_cannot_delete_event(client):
    """Unauthenticated requests are rejected with 401."""
    del_res = await client.delete("/api/v1/events/some-uuid-1234")
    assert del_res.status_code == 401


@pytest.mark.asyncio
async def test_repeat_delete_or_nonexistent_returns_404(client):
    """Deleting a non-existent or already deleted event returns 404 Not Found."""
    owner_init = make_test_init_data(user_id=7104, username="owner_7104")
    owner_headers = {"Authorization": f"tma {owner_init}"}

    # Non-existent ID
    res_fake = await client.delete("/api/v1/events/non-existent-id-000", headers=owner_headers)
    assert res_fake.status_code == 404

    # Create & delete real event
    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Standup Show",
            "description": "Comedy evening.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": "2026-11-27T19:00:00Z",
            "venue_name": "Comedy Hall",
            "address": "пр. Расула Гамзатова, 15"
        },
        headers=owner_headers
    )
    assert create_res.status_code == 201
    event_id = create_res.json()["id"]

    first_del = await client.delete(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert first_del.status_code == 200

    # Repeat delete returns 404
    second_del = await client.delete(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert second_del.status_code == 404


@pytest.mark.asyncio
async def test_deleted_event_disappears_from_feed_and_discovery(client, test_session):
    """
    When an event is published, it appears in public feed and unified search.
    When deleted, it immediately disappears from both.
    """
    owner_init = make_test_init_data(user_id=7105, username="owner_7105")
    owner_headers = {"Authorization": f"tma {owner_init}"}

    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Unique Jazz Night 999",
            "description": "Live smooth jazz and saxophone solos in the garden.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": "2026-11-28T19:30:00Z",
            "venue_name": "Botanical Lounge",
            "address": "ул. Коркмасова, 8"
        },
        headers=owner_headers
    )
    event_id = create_res.json()["id"]

    # Publish event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Verify present in public feed
    feed_res = await client.get("/api/v1/events?city_id=makhachkala")
    assert feed_res.status_code == 200
    assert any(e["id"] == event_id for e in feed_res.json()["events"])

    # Verify present in discovery search
    search_res = await client.get("/api/v1/discovery/search?q=Unique+Jazz+Night+999")
    assert search_res.status_code == 200
    assert any(e["id"] == event_id for e in search_res.json()["events"])

    # Organizer deletes the event
    del_res = await client.delete(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert del_res.status_code == 200

    # Disappears from public feed
    feed_after = await client.get("/api/v1/events?city_id=makhachkala")
    assert not any(e["id"] == event_id for e in feed_after.json()["events"])

    # Disappears from discovery search
    search_after = await client.get("/api/v1/discovery/search?q=Unique+Jazz+Night+999")
    assert not any(e["id"] == event_id for e in search_after.json()["events"])


@pytest.mark.asyncio
async def test_deleted_event_disappears_from_personal_events(client, test_session):
    """
    Users who marked 'Я иду' or 'Хочу пойти' no longer see the event in their Personal Events Hub
    once it has been deleted by the organizer.
    """
    owner_init = make_test_init_data(user_id=7106, username="owner_7106")
    attending_init = make_test_init_data(user_id=7107, username="attendee_7107")
    interested_init = make_test_init_data(user_id=7108, username="interested_7108")

    owner_headers = {"Authorization": f"tma {owner_init}"}
    attending_headers = {"Authorization": f"tma {attending_init}"}
    interested_headers = {"Authorization": f"tma {interested_init}"}

    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Community Workshop 2026",
            "description": "Design thinking and innovation session.",
            "category_id": "education",
            "city_id": "makhachkala",
            "start_at": "2026-11-29T14:00:00Z",
            "venue_name": "Coworking Space",
            "address": "пр. Акушинского, 24"
        },
        headers=owner_headers
    )
    event_id = create_res.json()["id"]

    # Publish event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # User 7107 confirms RSVP ("Я иду")
    rsvp_res = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=attending_headers)
    assert rsvp_res.status_code == 200

    # User 7108 confirms Interest ("Хочу пойти")
    int_res = await client.post(f"/api/v1/events/{event_id}/interest", headers=interested_headers)
    assert int_res.status_code == 200

    # Both verify presence in personal events
    att_personal = await client.get("/api/v1/users/me/events?type=attending", headers=attending_headers)
    assert any(e["id"] == event_id for e in att_personal.json())

    int_personal = await client.get("/api/v1/users/me/events?type=interested", headers=interested_headers)
    assert any(e["id"] == event_id for e in int_personal.json())

    # Organizer deletes the event
    del_res = await client.delete(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert del_res.status_code == 200

    # Disappears from both users' personal hub
    att_personal_after = await client.get("/api/v1/users/me/events?type=attending", headers=attending_headers)
    assert not any(e["id"] == event_id for e in att_personal_after.json())

    int_personal_after = await client.get("/api/v1/users/me/events?type=interested", headers=interested_headers)
    assert not any(e["id"] == event_id for e in int_personal_after.json())


@pytest.mark.asyncio
async def test_cannot_rsvp_or_interest_deleted_event(client, test_session):
    """Interactions with a deleted event return 404."""
    owner_init = make_test_init_data(user_id=7109, username="owner_7109")
    user_init = make_test_init_data(user_id=7110, username="user_7110")
    owner_headers = {"Authorization": f"tma {owner_init}"}
    user_headers = {"Authorization": f"tma {user_init}"}

    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Expired Exhibition",
            "description": "Modern digital art.",
            "category_id": "exhibitions",
            "city_id": "makhachkala",
            "start_at": "2026-11-30T10:00:00Z",
            "venue_name": "Gallery 1",
            "address": "ул. Горького, 3"
        },
        headers=owner_headers
    )
    assert create_res.status_code == 201
    event_id = create_res.json()["id"]

    # Delete event
    await client.delete(f"/api/v1/events/{event_id}", headers=owner_headers)

    # Attempt to RSVP
    rsvp_res = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=user_headers)
    assert rsvp_res.status_code == 404

    # Attempt to interest
    int_res = await client.post(f"/api/v1/events/{event_id}/interest", headers=user_headers)
    assert int_res.status_code == 404


@pytest.mark.asyncio
async def test_historical_attribution_preserved_on_delete(client, test_session):
    """
    Deleting an event soft-deletes it (status='deleted') but preserves
    historical attendee, interest, and view records.
    """
    owner_init = make_test_init_data(user_id=7111, username="owner_7111")
    user_init = make_test_init_data(user_id=7112, username="user_7112")
    owner_headers = {"Authorization": f"tma {owner_init}"}
    user_headers = {"Authorization": f"tma {user_init}"}

    create_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Historic Rock Concert",
            "description": "Heavy metal live show.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": "2026-12-01T20:00:00Z",
            "venue_name": "Rock Club",
            "address": "ул. Батырая, 12"
        },
        headers=owner_headers
    )
    event_id = create_res.json()["id"]

    # Publish event
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # User RSVPs and views
    rsvp_res = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=user_headers)
    assert rsvp_res.status_code == 200
    view_res = await client.post(f"/api/v1/events/{event_id}/view", json={"source": "discovery"}, headers=user_headers)
    assert view_res.status_code == 200

    user_db = (await test_session.execute(select(User).where(User.telegram_id == 7112))).scalar_one()

    # Verify rows exist in DB
    att_row = (await test_session.execute(
        select(EventAttendee).where(EventAttendee.event_id == event_id, EventAttendee.user_id == user_db.id)
    )).scalar_one_or_none()
    assert att_row is not None

    view_row = (await test_session.execute(
        select(EventView).where(EventView.event_id == event_id, EventView.user_id == user_db.id)
    )).scalar_one_or_none()
    assert view_row is not None

    # Organizer deletes the event
    del_res = await client.delete(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert del_res.status_code == 200

    # Verify event status in DB is 'deleted'
    ev_after = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    assert ev_after.status == EventStatus.DELETED.value

    # Verify historical attendee and view rows STILL exist
    att_after = (await test_session.execute(
        select(EventAttendee).where(EventAttendee.event_id == event_id, EventAttendee.user_id == user_db.id)
    )).scalar_one_or_none()
    assert att_after is not None

    view_after = (await test_session.execute(
        select(EventView).where(EventView.event_id == event_id, EventView.user_id == user_db.id)
    )).scalar_one_or_none()
    assert view_after is not None
