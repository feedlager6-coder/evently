import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.models.organization import Organization
from app.models.event import Event, EventStatus
from app.models.interest import EventInterest
from app.models.attendee import EventAttendee
from app.models.subscription import Subscription
from app.models.view import EventView
from app.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    RecipientStatus,
)


def make_event_payload(org_id: str, title: str = "Live Acoustic Concert", days: int = 5):
    return {
        "title": title,
        "description": "Live musical performance with high quality acoustic sound.",
        "category_id": "concerts",
        "city_id": "makhachkala",
        "start_at": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
        "organization_id": org_id,
        "venue_name": "Main Concert Hall",
    }


@pytest.mark.asyncio
async def test_organizer_insights_endpoint_empty_state(client, test_session):
    """
    Verifies that an organizer with zero events, zero organizations, and zero broadcasts
    receives a valid 200 OK response with zeroed metrics and has_data=False.
    """
    user_id = 15001
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='fresh_organizer')}"}

    res = await client.get("/api/v1/organizer/insights", headers=auth_header)
    assert res.status_code == 200
    data = res.json()

    assert data["has_data"] is False
    assert "Создайте первое событие" in data["fact_sentence"]
    assert data["audience"]["total_subscribers"] == 0
    assert data["audience"]["new_subscribers_7d"] == 0
    assert data["audience"]["new_subscribers_30d"] == 0
    assert data["audience"]["total_unique_engaged"] == 0

    assert data["events"]["total_events"] == 0
    assert data["events"]["upcoming_events_count"] == 0
    assert data["events"]["past_events_count"] == 0
    assert data["events"]["total_views"] == 0
    assert data["events"]["total_interest"] == 0
    assert data["events"]["total_rsvps"] == 0

    assert data["broadcasts"]["total_broadcasts"] == 0
    assert data["broadcasts"]["total_delivered"] == 0
    assert data["broadcasts"]["total_opened"] == 0
    assert data["broadcasts"]["total_attributed_interest"] == 0
    assert data["broadcasts"]["total_attributed_rsvp"] == 0
    assert data["broadcasts"]["overall_open_rate"] == 0.0

    assert data["sources"] == []


@pytest.mark.asyncio
async def test_organizer_insights_audience_growth(client, test_session):
    """
    Verifies audience metrics: total subscribers, 7d velocity, 30d velocity, and unique engaged reach.
    """
    owner_id = 15002
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='audience_owner')}"}

    # 1. Create Organization
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Audience Club", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    now = datetime.now(timezone.utc)
    # 2. Add 3 subscriptions directly to db with different timestamps
    # Sub 1: 3 days ago (< 7d)
    sub1 = Subscription(user_id=15101, organization_id=org_id, created_at=now - timedelta(days=3))
    # Sub 2: 15 days ago (< 30d, > 7d)
    sub2 = Subscription(user_id=15102, organization_id=org_id, created_at=now - timedelta(days=15))
    # Sub 3: 45 days ago (> 30d)
    sub3 = Subscription(user_id=15103, organization_id=org_id, created_at=now - timedelta(days=45))

    test_session.add_all([sub1, sub2, sub3])
    await test_session.commit()

    res = await client.get("/api/v1/organizer/insights", headers=auth_owner)
    assert res.status_code == 200
    data = res.json()

    assert data["has_data"] is True
    assert data["audience"]["total_subscribers"] == 3
    assert data["audience"]["new_subscribers_7d"] == 1
    assert data["audience"]["new_subscribers_30d"] == 2
    assert data["audience"]["total_unique_engaged"] == 3


@pytest.mark.asyncio
async def test_organizer_insights_events_totals(client, test_session):
    """
    Verifies event performance totals: upcoming, past, total views, total interest, total rsvps.
    """
    owner_id = 15003
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='events_owner')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Events Arena", "category": "Спорт", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    now = datetime.now(timezone.utc)

    # Event 1: upcoming published
    ev1 = Event(
        title="Upcoming Match",
        description="Great match description here.",
        category_id="sports",
        city_id="makhachkala",
        venue_name="Stadium",
        address="Central Ave 1",
        start_at=now + timedelta(days=2),
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=owner_id,
        organization_id=org_id,
    )
    # Event 2: upcoming pending
    ev2 = Event(
        title="Pending Tournament",
        description="Tournament description here.",
        category_id="sports",
        city_id="makhachkala",
        venue_name="Arena",
        address="Sport St 5",
        start_at=now + timedelta(days=10),
        status=EventStatus.PENDING.value,
        organizer_user_id=owner_id,
        organization_id=org_id,
    )
    # Event 3: past published
    ev3 = Event(
        title="Past Marathon",
        description="Marathon description here.",
        category_id="sports",
        city_id="makhachkala",
        venue_name="Park",
        address="Parkway 10",
        start_at=now - timedelta(days=5),
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=owner_id,
        organization_id=org_id,
    )

    test_session.add_all([ev1, ev2, ev3])
    await test_session.commit()
    await test_session.refresh(ev1)
    await test_session.refresh(ev2)
    await test_session.refresh(ev3)

    # Add interactions: views, interests, attendees
    v1 = EventView(event_id=ev1.id, user_id=15201, source="discovery")
    v2 = EventView(event_id=ev1.id, user_id=15202, source="deep_link")
    v3 = EventView(event_id=ev3.id, user_id=15203, source="discovery")

    int1 = EventInterest(event_id=ev1.id, user_id=15201)
    int2 = EventInterest(event_id=ev1.id, user_id=15204)

    att1 = EventAttendee(event_id=ev1.id, user_id=15201)
    att2 = EventAttendee(event_id=ev3.id, user_id=15205)

    test_session.add_all([v1, v2, v3, int1, int2, att1, att2])
    await test_session.commit()

    res = await client.get("/api/v1/organizer/insights", headers=auth_owner)
    assert res.status_code == 200
    data = res.json()

    assert data["events"]["total_events"] == 3
    assert data["events"]["upcoming_events_count"] == 2
    assert data["events"]["past_events_count"] == 1
    assert data["events"]["total_views"] == 3
    assert data["events"]["total_interest"] == 2
    assert data["events"]["total_rsvps"] == 2


@pytest.mark.asyncio
async def test_organizer_insights_broadcast_attribution_totals(client, test_session):
    """
    Verifies broadcast attribution aggregation: delivered, opened, attributed interest, attributed rsvp,
    and conversion rates with zero-division safety.
    """
    owner_id = 15004
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='bcast_owner')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Broadcast Club", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    now = datetime.now(timezone.utc)
    ev = Event(
        title="Rock Festival",
        description="Rock festival description.",
        category_id="concerts",
        city_id="makhachkala",
        venue_name="Open Air Stage",
        address="Coast St 1",
        start_at=now + timedelta(days=7),
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=owner_id,
        organization_id=org_id,
    )
    test_session.add(ev)
    await test_session.commit()
    await test_session.refresh(ev)

    # Create Broadcast
    bcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_id,
        event_id=ev.id,
        status=BroadcastStatus.COMPLETED.value,
        total_recipients=10,
        sent_count=10,
        delivered_count=10,
        attribution_token="tok_15004_test",
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    # 4 recipients:
    # Rec 1: delivered, opened, interest, rsvp
    # Rec 2: delivered, opened, interest
    # Rec 3: delivered, opened
    # Rec 4: delivered only
    r1 = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=15301,
        status=RecipientStatus.SENT.value,
        opened_at=now,
        attributed_interest_at=now,
        attributed_rsvp_at=now,
    )
    r2 = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=15302,
        status=RecipientStatus.SENT.value,
        opened_at=now,
        attributed_interest_at=now,
    )
    r3 = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=15303,
        status=RecipientStatus.SENT.value,
        opened_at=now,
    )
    r4 = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=15304,
        status=RecipientStatus.SENT.value,
    )
    test_session.add_all([r1, r2, r3, r4])
    await test_session.commit()

    res = await client.get("/api/v1/organizer/insights", headers=auth_owner)
    assert res.status_code == 200
    data = res.json()

    b_data = data["broadcasts"]
    assert b_data["total_broadcasts"] == 1
    assert b_data["total_delivered"] == 10
    assert b_data["total_opened"] == 3
    assert b_data["total_attributed_interest"] == 2
    assert b_data["total_attributed_rsvp"] == 1
    # 3 / 10 = 30.0%
    assert b_data["overall_open_rate"] == 30.0
    # 2 / 10 = 20.0%
    assert b_data["overall_interest_conversion"] == 20.0
    # 1 / 10 = 10.0%
    assert b_data["overall_rsvp_conversion"] == 10.0

    # Fact sentence should mention broadcast results
    assert "Рассылки принесли 3 переходов и 1 подтвержденных гостей" in data["fact_sentence"]


@pytest.mark.asyncio
async def test_broadcast_vs_event_totals_distinction(client, test_session):
    """
    CRITICAL INVARIANT TEST:
    Verifies that total event metrics (views, interest, attendee) are independent
    and NOT conflated with broadcast-attributed metrics.
    """
    owner_id = 15005
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='distinction_owner')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Theater Center", "category": "Театр", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    now = datetime.now(timezone.utc)
    ev = Event(
        title="Hamlet Drama",
        description="Shakespeare drama performance.",
        category_id="theatre",
        city_id="makhachkala",
        venue_name="Drama Theater",
        address="Theater Square 2",
        start_at=now + timedelta(days=4),
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=owner_id,
        organization_id=org_id,
    )
    test_session.add(ev)
    await test_session.commit()
    await test_session.refresh(ev)

    # 10 Organic Views
    for i in range(10):
        test_session.add(EventView(event_id=ev.id, user_id=15400 + i, source="discovery"))

    # 5 Organic Interests
    for i in range(5):
        test_session.add(EventInterest(event_id=ev.id, user_id=15400 + i))

    # 4 Organic Attendees
    for i in range(4):
        test_session.add(EventAttendee(event_id=ev.id, user_id=15400 + i))

    # 1 Broadcast with 2 delivered, 1 open, 1 attributed RSVP
    bcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=owner_id,
        event_id=ev.id,
        status=BroadcastStatus.COMPLETED.value,
        total_recipients=2,
        sent_count=2,
        delivered_count=2,
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    r1 = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=15450,
        status=RecipientStatus.SENT.value,
        opened_at=now,
        attributed_rsvp_at=now,
    )
    r2 = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=15451,
        status=RecipientStatus.SENT.value,
    )
    test_session.add_all([r1, r2])
    await test_session.commit()

    res = await client.get("/api/v1/organizer/insights", headers=auth_owner)
    data = res.json()

    # Total Event metrics
    assert data["events"]["total_views"] == 10
    assert data["events"]["total_interest"] == 5
    assert data["events"]["total_rsvps"] == 4

    # Broadcast-attributed metrics
    assert data["broadcasts"]["total_delivered"] == 2
    assert data["broadcasts"]["total_opened"] == 1
    assert data["broadcasts"]["total_attributed_rsvp"] == 1

    # Invariant: Total event counts and broadcast-attributed counts are distinct
    assert data["events"]["total_views"] != data["broadcasts"]["total_opened"]
    assert data["events"]["total_rsvps"] != data["broadcasts"]["total_attributed_rsvp"]


@pytest.mark.asyncio
async def test_sources_breakdown(client, test_session):
    """
    Verifies that EventView sources are grouped with correct labels, counts, and percentages.
    """
    owner_id = 15006
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='sources_owner')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Analytics Hall", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    now = datetime.now(timezone.utc)
    ev = Event(
        title="Jazz Night",
        description="Smooth jazz live performance.",
        category_id="concerts",
        city_id="makhachkala",
        venue_name="Jazz Club",
        address="Dadaeva 1",
        start_at=now + timedelta(days=3),
        status=EventStatus.PUBLISHED.value,
        organizer_user_id=owner_id,
        organization_id=org_id,
    )
    test_session.add(ev)
    await test_session.commit()
    await test_session.refresh(ev)

    # Views: 6 discovery, 3 broadcast, 1 deep_link = 10 total
    for i in range(6):
        test_session.add(EventView(event_id=ev.id, user_id=15500 + i, source="discovery"))
    for i in range(3):
        test_session.add(EventView(event_id=ev.id, user_id=15510 + i, source="broadcast"))
    test_session.add(EventView(event_id=ev.id, user_id=15520, source="deep_link"))

    await test_session.commit()

    res = await client.get("/api/v1/organizer/insights", headers=auth_owner)
    assert res.status_code == 200
    data = res.json()

    sources = data["sources"]
    assert len(sources) == 3

    # Sorted descending by views_count
    assert sources[0]["source"] == "discovery"
    assert sources[0]["label"] == "Афиша"
    assert sources[0]["views_count"] == 6
    assert sources[0]["percentage"] == 60.0

    assert sources[1]["source"] == "broadcast"
    assert sources[1]["label"] == "Рассылки"
    assert sources[1]["views_count"] == 3
    assert sources[1]["percentage"] == 30.0

    assert sources[2]["source"] == "deep_link"
    assert sources[2]["label"] == "Прямая ссылка"
    assert sources[2]["views_count"] == 1
    assert sources[2]["percentage"] == 10.0


@pytest.mark.asyncio
async def test_event_summary_includes_broadcast_attribution(client, test_session):
    """
    Verifies that GET /api/v1/organizer/events returns EventSummary objects
    enriched with broadcast_opens_count, broadcast_interest_count, and broadcast_rsvp_count.
    """
    owner_id = 15007
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='ev_summary_owner')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Attribution Space", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    res_ev = await client.post(
        "/api/v1/events",
        json=make_event_payload(org_id, "Cinema Evening", 2),
        headers=auth_owner,
    )
    assert res_ev.status_code == 201
    event_id = res_ev.json()["id"]

    # Load event from DB
    ev = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev.status = EventStatus.PUBLISHED.value
    await test_session.commit()
    await test_session.refresh(ev)

    now = datetime.now(timezone.utc)
    bcast = Broadcast(
        organization_id=org_id,
        created_by_user_id=ev.organizer_user_id,
        event_id=ev.id,
        status=BroadcastStatus.COMPLETED.value,
        total_recipients=5,
        delivered_count=5,
    )
    test_session.add(bcast)
    await test_session.commit()
    await test_session.refresh(bcast)

    rec = BroadcastRecipient(
        broadcast_id=bcast.id,
        user_id=ev.organizer_user_id,
        status=RecipientStatus.SENT.value,
        opened_at=now,
        attributed_interest_at=now,
        attributed_rsvp_at=now,
    )
    test_session.add(rec)
    await test_session.commit()

    res = await client.get("/api/v1/organizer/events", headers=auth_owner)
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 1

    ev_item = next((e for e in events if e["id"] == ev.id), None)
    assert ev_item is not None
    assert ev_item["broadcast_opens_count"] == 1
    assert ev_item["broadcast_interest_count"] == 1
    assert ev_item["broadcast_rsvp_count"] == 1


@pytest.mark.asyncio
async def test_organizer_insights_authorization(client, test_session):
    """
    Verifies that unauthenticated calls return 401, and that organizers
    only see their own data.
    """
    # 1. Unauthenticated request
    res_unauth = await client.get("/api/v1/organizer/insights")
    assert res_unauth.status_code == 401

    # 2. Organizer A and Organizer B data isolation
    user_a = 15008
    user_b = 15009
    auth_a = {"Authorization": f"tma {make_test_init_data(user_id=user_a, username='org_a')}"}
    auth_b = {"Authorization": f"tma {make_test_init_data(user_id=user_b, username='org_b')}"}

    # Organizer A creates org & subscriber
    res_org_a = await client.post(
        "/api/v1/organizations",
        json={"name": "Org A", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_a,
    )
    org_a_id = res_org_a.json()["id"]
    test_session.add(Subscription(user_id=15701, organization_id=org_a_id))
    await test_session.commit()

    # Organizer B checks insights -> should have 0 subscribers
    res_b = await client.get("/api/v1/organizer/insights", headers=auth_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["audience"]["total_subscribers"] == 0
    assert data_b["events"]["total_events"] == 0
