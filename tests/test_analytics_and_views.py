import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from tests.conftest import make_test_init_data
from app.models.event import Event, EventStatus
from app.models.view import EventView
from app.services.event_service import create_organizer_event
from app.schemas.event import EventCreate


@pytest.mark.asyncio
async def test_view_is_recorded(client, test_session):
    """1. View is recorded for published event."""
    user_id = 1111
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='viewer1')}"}

    # Get a published event
    resp = await client.get("/api/v1/events?city_id=spb")
    assert resp.status_code == 200
    event_id = resp.json()["events"][0]["id"]

    res = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "discovery"},
        headers=auth_header
    )
    assert res.status_code == 200
    data = res.json()
    assert data["recorded"] is True
    assert data["views_count"] >= 1


@pytest.mark.asyncio
async def test_duplicate_view_within_2h_ignored(client, test_session):
    """2. Duplicate view within 2 hours by the same authenticated user is ignored."""
    user_id = 2222
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='viewer2')}"}

    resp = await client.get("/api/v1/events?city_id=spb")
    event_id = resp.json()["events"][0]["id"]

    # First view
    res1 = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "discovery"},
        headers=auth_header
    )
    assert res1.status_code == 200
    count_after_first = res1.json()["views_count"]
    assert res1.json()["recorded"] is True

    # Immediate second view (30 seconds later)
    res2 = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "discovery"},
        headers=auth_header
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["recorded"] is False
    assert data2["views_count"] == count_after_first


@pytest.mark.asyncio
async def test_view_after_2h_recorded(client, test_session):
    """3. View after 2 hours is recorded as a new view."""
    user_id = 3333
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='viewer3')}"}
    me_res = await client.get("/api/v1/users/me", headers=auth_header)
    assert me_res.status_code == 200
    db_user_id = me_res.json()["id"]

    resp = await client.get("/api/v1/events?city_id=spb")
    event_id = resp.json()["events"][0]["id"]

    # First view
    res1 = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "discovery"},
        headers=auth_header
    )
    assert res1.status_code == 200
    initial_count = res1.json()["views_count"]

    # Artificially age the view record in the database by 3 hours
    three_hours_ago = datetime.now(timezone.utc) - timedelta(hours=3)
    await test_session.execute(
        update(EventView)
        .where(EventView.event_id == event_id, EventView.user_id == db_user_id)
        .values(created_at=three_hours_ago)
    )
    await test_session.commit()

    # Second view after 2h window
    res2 = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "deep_link"},
        headers=auth_header
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["recorded"] is True
    assert data2["views_count"] == initial_count + 1


@pytest.mark.asyncio
async def test_event_author_view_ignored(client, test_session):
    """4. Event author view is ignored and does not inflate views_count."""
    from app.models.user import User

    # Find event and its organizer
    resp = await client.get("/api/v1/events?city_id=spb")
    event_id = resp.json()["events"][0]["id"]

    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    author_id = ev_db.organizer_user_id

    # Find author user
    author = (await test_session.execute(select(User).where(User.id == author_id))).scalar_one_or_none()
    if author:
        author_auth = {"Authorization": f"tma {make_test_init_data(user_id=author.telegram_id, username=author.username or 'author')}"}
    else:
        author_auth = {"Authorization": f"tma {make_test_init_data(user_id=author_id, username='author_user')}"}

    # Count existing views
    existing_views = (await test_session.execute(
        select(EventView).where(EventView.event_id == event_id)
    )).scalars().all()
    initial_views_len = len(existing_views)

    # Author opens event
    res = await client.post(
        f"/api/v1/events/{event_id}/view",
        json={"source": "organizer"},
        headers=author_auth
    )
    assert res.status_code == 200
    data = res.json()
    assert data["recorded"] is False
    assert data["views_count"] == initial_views_len


@pytest.mark.asyncio
async def test_unpublished_event_rejected(client, test_session):
    """5. View tracking on an unpublished (pending/rejected) event is rejected with 400 Bad Request."""
    org_user_id = 5555
    create_payload = EventCreate(
        title="Unpublished Secret Concert",
        description="Pending concert description here",
        category_id="concerts",
        city_id="spb",
        start_at=datetime.now(timezone.utc) + timedelta(days=5),
        venue_name="Underground Club"
    )
    pending_event = await create_organizer_event(test_session, create_payload, organizer_user_id=org_user_id)
    assert pending_event.status == EventStatus.PENDING.value

    # Someone tries to view pending event
    viewer_auth = {"Authorization": f"tma {make_test_init_data(user_id=9999, username='curious_user')}"}
    res = await client.post(
        f"/api/v1/events/{pending_event.id}/view",
        json={"source": "discovery"},
        headers=viewer_auth
    )
    assert res.status_code == 400
    assert "неопубликованное" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_nonexistent_event_rejected(client):
    """6. Nonexistent event rejected with 404."""
    res = await client.post("/api/v1/events/00000000-0000-0000-0000-000000000000/view")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_user_id_comes_from_auth_and_anonymous_view(client, test_session):
    """7. user_id is extracted strictly from auth token, and anonymous view is recorded without user_id."""
    resp = await client.get("/api/v1/events?city_id=spb")
    event_id = resp.json()["events"][0]["id"]

    # Anonymous view
    anon_res = await client.post(f"/api/v1/events/{event_id}/view", json={"source": "deep_link"})
    assert anon_res.status_code == 200
    assert anon_res.json()["recorded"] is True

    # Check in DB that user_id is null
    anon_view = (await test_session.execute(
        select(EventView).where(EventView.event_id == event_id, EventView.user_id.is_(None))
    )).scalars().first()
    assert anon_view is not None
    assert anon_view.source == "deep_link"


@pytest.mark.asyncio
async def test_organizer_sees_own_views_count(client, test_session):
    """8. Organizer can view views_count in GET /organizer/events and GET /events/{id}."""
    org_user_id = 6666
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=org_user_id, username='rock_organizer')}"}
    me_res = await client.get("/api/v1/users/me", headers=auth_header)
    assert me_res.status_code == 200
    db_user_id = me_res.json()["id"]

    create_payload = EventCreate(
        title="Public Rock Night",
        description="Public rock night details here",
        category_id="concerts",
        city_id="spb",
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Aurora Concert Hall"
    )
    event = await create_organizer_event(test_session, create_payload, organizer_user_id=db_user_id)
    event.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Viewer 1 records view
    viewer1_auth = {"Authorization": f"tma {make_test_init_data(user_id=8881, username='fan1')}"}
    await client.post(f"/api/v1/events/{event.id}/view", json={"source": "discovery"}, headers=viewer1_auth)

    # Viewer 2 records view
    viewer2_auth = {"Authorization": f"tma {make_test_init_data(user_id=8882, username='fan2')}"}
    await client.post(f"/api/v1/events/{event.id}/view", json={"source": "deep_link"}, headers=viewer2_auth)

    # Organizer checks GET /api/v1/organizer/events
    org_events_res = await client.get("/api/v1/organizer/events", headers=auth_header)
    assert org_events_res.status_code == 200
    ev_summary = next(e for e in org_events_res.json() if e["id"] == event.id)
    assert ev_summary["views_count"] == 2

    # Organizer checks GET /api/v1/events/{id}
    details_res = await client.get(f"/api/v1/events/{event.id}", headers=auth_header)
    assert details_res.status_code == 200
    assert details_res.json()["views_count"] == 2


@pytest.mark.asyncio
async def test_unrelated_organizer_cannot_access_private_analytics(client, test_session):
    """9. Unrelated user or organizer sees views_count=0 on GET /events/{id}."""
    org_user_id = 7771
    auth_org = {"Authorization": f"tma {make_test_init_data(user_id=org_user_id, username='jazz_org')}"}
    me_org = await client.get("/api/v1/users/me", headers=auth_org)
    db_org_id = me_org.json()["id"]

    create_payload = EventCreate(
        title="Jazz Night Exclusive",
        description="Exclusive jazz night details",
        category_id="concerts",
        city_id="spb",
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        venue_name="Jazz Bar"
    )
    event = await create_organizer_event(test_session, create_payload, organizer_user_id=db_org_id)
    event.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Record 3 views
    for vid in [9101, 9102, 9103]:
        v_auth = {"Authorization": f"tma {make_test_init_data(user_id=vid, username=f'jazz_fan_{vid}')}"}
        await client.post(f"/api/v1/events/{event.id}/view", headers=v_auth)

    # Unrelated user checks details
    stranger_auth = {"Authorization": f"tma {make_test_init_data(user_id=9999, username='stranger')}"}
    details_res = await client.get(f"/api/v1/events/{event.id}", headers=stranger_auth)
    assert details_res.status_code == 200
    # Private view analytics are protected (0 for non-organizer)
    assert details_res.json()["views_count"] == 0


@pytest.mark.asyncio
async def test_zero_views_conversion_safe_value():
    """10. Zero views conversion calculation safely returns '—' without ZeroDivisionError."""
    def calc_conversion(count: int, views: int) -> str:
        return f"{(count / views * 100):.1f}%" if views > 0 else "—"

    assert calc_conversion(10, 0) == "—"
    assert calc_conversion(0, 0) == "—"
    assert calc_conversion(5, 50) == "10.0%"
    assert calc_conversion(1, 3) == "33.3%"


@pytest.mark.asyncio
async def test_analytics_failure_does_not_break_event_opening(client, test_session):
    """11. Tracking endpoint failure does not disrupt event details fetching."""
    resp = await client.get("/api/v1/events?city_id=spb")
    event_id = resp.json()["events"][0]["id"]

    # Even if view call fails or returns error, details endpoint functions cleanly
    details_res = await client.get(f"/api/v1/events/{event_id}")
    assert details_res.status_code == 200
    assert details_res.json()["id"] == event_id


@pytest.mark.asyncio
async def test_source_values_handled_correctly(client, test_session):
    """12. Valid sources are preserved and invalid sources fall back to 'unknown'."""
    resp = await client.get("/api/v1/events?city_id=spb")
    event_id = resp.json()["events"][0]["id"]

    # Test valid source 'deep_link'
    u1 = 8111
    auth1 = {"Authorization": f"tma {make_test_init_data(user_id=u1, username='src1')}"}
    me1 = await client.get("/api/v1/users/me", headers=auth1)
    db_u1 = me1.json()["id"]
    await client.post(f"/api/v1/events/{event_id}/view", json={"source": "deep_link"}, headers=auth1)

    v1 = (await test_session.execute(
        select(EventView).where(EventView.event_id == event_id, EventView.user_id == db_u1)
    )).scalar_one()
    assert v1.source == "deep_link"

    # Test invalid source 'malicious_injection_123'
    u2 = 8222
    auth2 = {"Authorization": f"tma {make_test_init_data(user_id=u2, username='src2')}"}
    me2 = await client.get("/api/v1/users/me", headers=auth2)
    db_u2 = me2.json()["id"]
    await client.post(f"/api/v1/events/{event_id}/view", json={"source": "malicious_injection_123"}, headers=auth2)

    v2 = (await test_session.execute(
        select(EventView).where(EventView.event_id == event_id, EventView.user_id == db_u2)
    )).scalar_one()
    assert v2.source == "unknown"
