import pytest
from datetime import datetime, timedelta, timezone
from tests.conftest import make_test_init_data
from app.models.event import Event, EventStatus
from app.services.event_service import create_organizer_event
from app.schemas.event import EventCreate


@pytest.mark.asyncio
async def test_personal_events_unauthorized_fails(client):
    res = await client.get("/api/v1/users/me/events?type=attending")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_personal_events_attending_and_interested(client, test_session):
    # 1. Setup user 777
    user_id = 777
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='planner_alex')}"}

    # Get published events
    resp = await client.get("/api/v1/events?city_id=spb")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) >= 2

    event_attending = events[0]
    event_interested = events[1]

    # User marks event_attending as "Я иду"
    rsvp_res = await client.post(f"/api/v1/events/{event_attending['id']}/rsvp", headers=auth_header)
    assert rsvp_res.status_code == 200

    # User marks event_interested as "Хочу пойти"
    int_res = await client.post(f"/api/v1/events/{event_interested['id']}/interest", headers=auth_header)
    assert int_res.status_code == 200

    # 2. Query attending personal events
    att_res = await client.get("/api/v1/users/me/events?type=attending", headers=auth_header)
    assert att_res.status_code == 200
    att_list = att_res.json()
    att_ids = [e["id"] for e in att_list]
    assert event_attending["id"] in att_ids
    assert event_interested["id"] not in att_ids

    # Check flags on returned item
    matching_att = next(e for e in att_list if e["id"] == event_attending["id"])
    assert matching_att["is_attending"] is True

    # 3. Query interested personal events
    int_list_res = await client.get("/api/v1/users/me/events?type=interested", headers=auth_header)
    assert int_list_res.status_code == 200
    int_list = int_list_res.json()
    int_ids = [e["id"] for e in int_list]
    assert event_interested["id"] in int_ids
    assert event_attending["id"] not in int_ids

    # Check flags on returned item
    matching_int = next(e for e in int_list if e["id"] == event_interested["id"])
    assert matching_int["current_user_interested"] is True


@pytest.mark.asyncio
async def test_personal_events_isolation_between_users(client):
    user_a = 8881
    user_b = 8882

    auth_a = {"Authorization": f"tma {make_test_init_data(user_id=user_a, username='user_a')}"}
    auth_b = {"Authorization": f"tma {make_test_init_data(user_id=user_b, username='user_b')}"}

    # Get events
    events = (await client.get("/api/v1/events?city_id=makhachkala")).json()["events"]
    target_event = events[0]

    # User A RSVPs
    await client.post(f"/api/v1/events/{target_event['id']}/rsvp", headers=auth_a)

    # User A sees it
    res_a = await client.get("/api/v1/users/me/events?type=attending", headers=auth_a)
    assert res_a.status_code == 200
    assert any(e["id"] == target_event["id"] for e in res_a.json())

    # User B does NOT see it
    res_b = await client.get("/api/v1/users/me/events?type=attending", headers=auth_b)
    assert res_b.status_code == 200
    assert not any(e["id"] == target_event["id"] for e in res_b.json())


@pytest.mark.asyncio
async def test_organizer_events_includes_interest_count(client, test_session):
    # 1. Create organizer and event
    org_user_id = 9991
    org_auth = {"Authorization": f"tma {make_test_init_data(user_id=org_user_id, username='event_maker')}"}

    # First authenticate user via /users/me so user record exists in DB
    me_res = await client.get("/api/v1/users/me", headers=org_auth)
    assert me_res.status_code == 200
    db_user_id = me_res.json()["id"]

    now = datetime.now(timezone.utc)
    ev_data = EventCreate(
        title="Jazz & Rooftop Summer Night",
        description="Exclusive jazz concert on the roof with saxophone quartet.",
        category_id="concerts",
        city_id="moscow",
        start_at=now + timedelta(days=5),
        venue_name="Sky Lounge Moscow",
        address="Тверская ул., 12",
        price_amount=1500.0,
        price_currency="RUB"
    )
    ev = await create_organizer_event(test_session, ev_data, organizer_user_id=db_user_id)

    # Initially 0 interest and 0 attendee
    org_events_res = await client.get("/api/v1/organizer/events", headers=org_auth)
    assert org_events_res.status_code == 200
    my_ev = next(e for e in org_events_res.json() if e["id"] == ev.id)
    assert my_ev["interest_count"] == 0
    assert my_ev["attendee_count"] == 0

    # Another user expresses interest
    fan_auth = {"Authorization": f"tma {make_test_init_data(user_id=9992, username='jazz_fan')}"}
    await client.post(f"/api/v1/events/{ev.id}/interest", headers=fan_auth)

    # Organizer events now reflects interest_count = 1
    org_events_res2 = await client.get("/api/v1/organizer/events", headers=org_auth)
    assert org_events_res2.status_code == 200
    my_ev2 = next(e for e in org_events_res2.json() if e["id"] == ev.id)
    assert my_ev2["interest_count"] == 1

