import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.models.event import Event, EventStatus
from app.models.interest import EventInterest
from app.models.attendee import EventAttendee
from app.services.event_service import (
    list_published_events,
    get_event_details,
    add_event_rsvp,
    remove_event_rsvp,
    add_event_interest,
    remove_event_interest,
    EventNotFoundError,
)
from conftest import make_test_init_data


@pytest.mark.asyncio
async def test_create_interest(test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    assert len(events) > 0
    event = events[0]
    initial_interest = event.interest_count
    user_id = 901

    is_int, count, is_att, att_count, msg = await add_event_interest(test_session, event.id, user_id=user_id)
    assert is_int is True
    assert count == initial_interest + 1
    assert is_att is False
    assert "confirmed" in msg.lower()

    # Verify get_event_details shows current_user_interested=True
    details = await get_event_details(test_session, event.id, current_user_id=user_id)
    assert details.current_user_interested is True
    assert details.interest_count == initial_interest + 1


@pytest.mark.asyncio
async def test_duplicate_interest_idempotency(test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event = events[0]
    initial_interest = event.interest_count
    user_id = 902

    # 1. First call
    is_int_1, count_1, _, _, msg_1 = await add_event_interest(test_session, event.id, user_id=user_id)
    assert is_int_1 is True
    assert count_1 == initial_interest + 1
    assert "confirmed" in msg_1.lower()

    # 2. Second call: idempotent, count does not increase
    is_int_2, count_2, _, _, msg_2 = await add_event_interest(test_session, event.id, user_id=user_id)
    assert is_int_2 is True
    assert count_2 == count_1
    assert "already interested" in msg_2.lower()


@pytest.mark.asyncio
async def test_delete_interest(test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event = events[0]
    initial_interest = event.interest_count
    user_id = 903

    # Add interest
    await add_event_interest(test_session, event.id, user_id=user_id)

    # Delete interest
    is_int, count, is_att, att_count, msg = await remove_event_interest(test_session, event.id, user_id=user_id)
    assert is_int is False
    assert count == initial_interest
    assert is_att is False
    assert "removed" in msg.lower()

    # Verify get_event_details reflects change
    details = await get_event_details(test_session, event.id, current_user_id=user_id)
    assert details.current_user_interested is False
    assert details.interest_count == initial_interest


@pytest.mark.asyncio
async def test_delete_interest_idempotency(test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event = events[0]
    user_id = 904

    # Remove when not interested
    is_int, count, is_att, _, msg = await remove_event_interest(test_session, event.id, user_id=user_id)
    assert is_int is False
    assert is_att is False
    assert "removed" in msg.lower()


@pytest.mark.asyncio
async def test_interest_to_rsvp_interaction(test_session):
    """When a user who expressed interest confirms RSVP ('Я иду'), the interest record is removed."""
    events, _ = await list_published_events(test_session, city_id="spb")
    event = events[0]
    user_id = 905

    # 1. Express interest
    await add_event_interest(test_session, event.id, user_id=user_id)
    d1 = await get_event_details(test_session, event.id, current_user_id=user_id)
    assert d1.current_user_interested is True
    assert d1.is_attending is False

    # 2. Confirm RSVP
    is_att, att_count, rsvp_msg = await add_event_rsvp(test_session, event.id, user_id=user_id)
    assert is_att is True

    # 3. Verify interest was cleared
    d2 = await get_event_details(test_session, event.id, current_user_id=user_id)
    assert d2.is_attending is True
    assert d2.current_user_interested is False


@pytest.mark.asyncio
async def test_rsvp_to_interest_interaction(test_session):
    """When an attendee clicks 'Хочу пойти', they switch from attending to interested."""
    events, _ = await list_published_events(test_session, city_id="spb")
    event = events[0]
    user_id = 906

    # 1. Attend event
    await add_event_rsvp(test_session, event.id, user_id=user_id)
    d1 = await get_event_details(test_session, event.id, current_user_id=user_id)
    assert d1.is_attending is True
    assert d1.current_user_interested is False

    # 2. Click 'Хочу пойти'
    is_int, int_count, is_att, att_count, msg = await add_event_interest(test_session, event.id, user_id=user_id)
    assert is_int is True
    assert is_att is False

    # 3. Verify attendance cleared and interest set
    d2 = await get_event_details(test_session, event.id, current_user_id=user_id)
    assert d2.is_attending is False
    assert d2.current_user_interested is True


@pytest.mark.asyncio
async def test_nonexistent_event_interest(test_session):
    with pytest.raises(EventNotFoundError):
        await add_event_interest(test_session, "non-existent-id", user_id=999)

    with pytest.raises(EventNotFoundError):
        await remove_event_interest(test_session, "non-existent-id", user_id=999)


@pytest.mark.asyncio
async def test_unique_constraint_db_level(test_session):
    """Verifies that inserting a duplicate (event_id, user_id) raises IntegrityError at the DB level."""
    events, _ = await list_published_events(test_session, city_id="spb")
    event = events[0]
    user_id = 907

    i1 = EventInterest(event_id=event.id, user_id=user_id)
    test_session.add(i1)
    await test_session.commit()

    i2 = EventInterest(event_id=event.id, user_id=user_id)
    test_session.add(i2)
    with pytest.raises(IntegrityError):
        await test_session.commit()
    await test_session.rollback()


@pytest.mark.asyncio
async def test_interest_http_endpoints(client, test_session):
    # Fetch an event id
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    # 1. Unauthorized POST -> 401
    res_no_auth = await client.post(f"/api/v1/events/{event_id}/interest")
    assert res_no_auth.status_code == 401

    # 2. Authorized POST -> 200
    init_data = make_test_init_data(user_id=8888)
    headers = {"Authorization": f"tma {init_data}"}

    res_post = await client.post(f"/api/v1/events/{event_id}/interest", headers=headers)
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["event_id"] == event_id
    assert data["is_interested"] is True
    assert data["interest_count"] >= 1
    assert data["is_attending"] is False

    # 3. Duplicate POST -> 200 (idempotent)
    res_post2 = await client.post(f"/api/v1/events/{event_id}/interest", headers=headers)
    assert res_post2.status_code == 200
    assert res_post2.json()["interest_count"] == data["interest_count"]

    # 4. Check GET /api/v1/events/{id} has current_user_interested=True
    res_get = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["current_user_interested"] is True

    # 5. Authorized DELETE -> 200
    res_del = await client.delete(f"/api/v1/events/{event_id}/interest", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["is_interested"] is False

    # 6. Check GET /api/v1/events/{id} has current_user_interested=False
    res_get2 = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert res_get2.status_code == 200
    assert res_get2.json()["current_user_interested"] is False

    # 7. Nonexistent event -> 404
    res_404 = await client.post("/api/v1/events/nonexistent-xyz/interest", headers=headers)
    assert res_404.status_code == 404
