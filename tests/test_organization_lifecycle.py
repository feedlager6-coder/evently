import pytest
import re
from pathlib import Path
from sqlalchemy import select
from app.models.organization import Organization
from app.models.event import Event, EventStatus
from tests.conftest import make_test_init_data


@pytest.mark.asyncio
async def test_owner_can_delete_organization(client):
    """Owner can delete their organization. Afterwards it is 404 and excluded from /me."""
    owner_init = make_test_init_data(user_id=8001, username="owner_8001")
    owner_headers = {"Authorization": f"tma {owner_init}"}

    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Org To Delete", "category": "Кафе", "city_id": "makhachkala"},
        headers=owner_headers
    )
    assert create_res.status_code == 201
    org_id = create_res.json()["id"]

    # Verify exists in /organizations/me
    me_res = await client.get("/api/v1/organizations/me", headers=owner_headers)
    assert any(o["id"] == org_id for o in me_res.json())

    # Delete organization
    del_res = await client.delete(f"/api/v1/organizations/{org_id}", headers=owner_headers)
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["ok"] is True
    assert "успешно удалена" in del_data["message"]

    # Public fetch returns 404
    get_res = await client.get(f"/api/v1/organizations/{org_id}")
    assert get_res.status_code == 404

    # Excluded from /organizations/me
    me_after = await client.get("/api/v1/organizations/me", headers=owner_headers)
    assert not any(o["id"] == org_id for o in me_after.json())


@pytest.mark.asyncio
async def test_non_owner_cannot_delete_organization(client):
    """Non-owner attempting to delete an organization is strictly rejected with 403."""
    owner_init = make_test_init_data(user_id=8002, username="owner_8002")
    intruder_init = make_test_init_data(user_id=8003, username="intruder_8003")
    owner_headers = {"Authorization": f"tma {owner_init}"}
    intruder_headers = {"Authorization": f"tma {intruder_init}"}

    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Secure Org", "category": "Бар", "city_id": "makhachkala"},
        headers=owner_headers
    )
    assert create_res.status_code == 201
    org_id = create_res.json()["id"]

    # Intruder tries to delete
    del_res = await client.delete(f"/api/v1/organizations/{org_id}", headers=intruder_headers)
    assert del_res.status_code == 403
    assert "не можете удалить чужую организацию" in del_res.json()["detail"]

    # Organization remains active and accessible
    get_res = await client.get(f"/api/v1/organizations/{org_id}")
    assert get_res.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_cannot_delete_organization(client):
    """Unauthenticated call to delete organization returns 401 Unauthorized."""
    del_res = await client.delete("/api/v1/organizations/any-org-id")
    assert del_res.status_code == 401


@pytest.mark.asyncio
async def test_nonexistent_organization_returns_404(client):
    """Attempting to delete a nonexistent organization returns 404."""
    user_init = make_test_init_data(user_id=8004, username="user_8004")
    headers = {"Authorization": f"tma {user_init}"}

    del_res = await client.delete("/api/v1/organizations/nonexistent-org-id-12345", headers=headers)
    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_deletion_requires_explicit_api_action_and_is_not_repeatable(client):
    """Calling DELETE once deletes the org; calling it again returns 404."""
    owner_init = make_test_init_data(user_id=8005, username="owner_8005")
    owner_headers = {"Authorization": f"tma {owner_init}"}

    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Explicit Org", "category": "Театр", "city_id": "makhachkala"},
        headers=owner_headers
    )
    org_id = create_res.json()["id"]

    # First delete succeeds
    del1 = await client.delete(f"/api/v1/organizations/{org_id}", headers=owner_headers)
    assert del1.status_code == 200

    # Second delete returns 404 (already deleted)
    del2 = await client.delete(f"/api/v1/organizations/{org_id}", headers=owner_headers)
    assert del2.status_code == 404


@pytest.mark.asyncio
async def test_linked_events_follow_safe_lifecycle(client):
    """
    When an organization is deleted:
    - Events linked to it are detached (organization_id = None).
    - Events are NOT deleted; they are preserved as personal events owned by organizer.
    - Organizer can still see them in /organizer/events.
    """
    owner_init = make_test_init_data(user_id=8006, username="owner_8006")
    owner_headers = {"Authorization": f"tma {owner_init}"}

    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Org With Events", "category": "Концертная площадка", "city_id": "makhachkala"},
        headers=owner_headers
    )
    org_id = org_res.json()["id"]

    # Create event linked to organization
    event_payload = {
        "title": "Acoustic Night",
        "description": "Acoustic concert featuring local indie artists and musicians.",
        "category_id": "concerts",
        "city_id": "makhachkala",
        "start_at": "2026-11-20T19:00:00Z",
        "venue_name": "Org Venue",
        "address": "ул. Пушкина, 10",
        "organization_id": org_id
    }
    ev_res = await client.post("/api/v1/events", json=event_payload, headers=owner_headers)
    assert ev_res.status_code == 201
    event_id = ev_res.json()["id"]
    assert ev_res.json()["organization_id"] == org_id

    # Delete organization
    del_res = await client.delete(f"/api/v1/organizations/{org_id}", headers=owner_headers)
    assert del_res.status_code == 200
    assert del_res.json()["detached_events_count"] == 1

    # Event still exists and is accessible
    ev_check = await client.get(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert ev_check.status_code == 200
    ev_data = ev_check.json()
    assert ev_data["title"] == "Acoustic Night"
    assert ev_data["organization_id"] is None
    assert ev_data["organization_name"] is None

    # Organizer still sees the event in their organized events
    my_events_res = await client.get("/api/v1/organizer/events", headers=owner_headers)
    assert my_events_res.status_code == 200
    my_event_ids = [e["id"] for e in my_events_res.json()]
    assert event_id in my_event_ids


@pytest.mark.asyncio
async def test_subscriptions_are_handled_safely(client):
    """
    When an organization is deleted:
    - Subscriptions are purged.
    - Subscribers no longer see the organization in /users/me/subscriptions.
    """
    owner_init = make_test_init_data(user_id=8007, username="owner_8007")
    sub_init = make_test_init_data(user_id=8008, username="subscriber_8008")
    owner_headers = {"Authorization": f"tma {owner_init}"}
    sub_headers = {"Authorization": f"tma {sub_init}"}

    # Create org
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Subscribed Club", "category": "Клуб", "city_id": "makhachkala"},
        headers=owner_headers
    )
    org_id = org_res.json()["id"]

    # Subscriber subscribes
    sub_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_headers)
    assert sub_res.status_code == 200
    assert sub_res.json()["is_subscribed"] is True

    # Verify present in user's subscriptions
    my_subs = await client.get("/api/v1/users/me/subscriptions", headers=sub_headers)
    assert any(s["organization"]["id"] == org_id for s in my_subs.json())

    # Owner deletes organization
    del_res = await client.delete(f"/api/v1/organizations/{org_id}", headers=owner_headers)
    assert del_res.status_code == 200

    # User's subscriptions list no longer contains the deleted organization
    my_subs_after = await client.get("/api/v1/users/me/subscriptions", headers=sub_headers)
    assert not any(s["organization"]["id"] == org_id for s in my_subs_after.json())


@pytest.mark.asyncio
async def test_historical_broadcasts_remain_safe_and_readable(client, test_session):
    """
    When an organization is deleted:
    - Historical broadcast records are preserved.
    - The organizer can still view past broadcasts in /organizer/broadcasts.
    """
    owner_init = make_test_init_data(user_id=8009, username="owner_8009")
    sub_init = make_test_init_data(user_id=8010, username="subscriber_8010")
    owner_headers = {"Authorization": f"tma {owner_init}"}
    sub_headers = {"Authorization": f"tma {sub_init}"}

    # 1. Create org
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Broadcast Org", "category": "Образование", "city_id": "makhachkala"},
        headers=owner_headers
    )
    org_id = org_res.json()["id"]

    # Upgrade to pro to allow broadcast creation
    from app.services.entitlement_service import EntitlementService
    await EntitlementService.set_organization_plan(test_session, org_id, plan="pro")

    # 2. Add subscriber
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_headers)

    # 3. Create broadcast
    bcast_res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Important historical announcement"
        },
        headers=owner_headers
    )
    assert bcast_res.status_code == 200
    broadcast_id = bcast_res.json()["id"]

    # 4. Owner deletes organization
    del_res = await client.delete(f"/api/v1/organizations/{org_id}", headers=owner_headers)
    assert del_res.status_code == 200

    # 5. Broadcasts list still contains the historical broadcast
    bcast_list = await client.get("/api/v1/organizer/broadcasts", headers=owner_headers)
    assert bcast_list.status_code == 200
    items = bcast_list.json()
    assert any(b["id"] == broadcast_id for b in items)

    # 6. Broadcast detail is still viewable by organizer
    detail_res = await client.get(f"/api/v1/organizer/broadcasts/{broadcast_id}", headers=owner_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == broadcast_id


@pytest.mark.asyncio
async def test_analytics_and_event_history_not_deleted(client, test_session):
    """
    When an organization is deleted:
    - Event views, interests, and RSVPs are not deleted.
    - Organizer insights totals remain accurate.
    """
    owner_init = make_test_init_data(user_id=8011, username="owner_8011")
    attendee_init = make_test_init_data(user_id=8012, username="attendee_8012")
    attendee2_init = make_test_init_data(user_id=8014, username="attendee_8014")
    owner_headers = {"Authorization": f"tma {owner_init}"}
    att_headers = {"Authorization": f"tma {attendee_init}"}
    att2_headers = {"Authorization": f"tma {attendee2_init}"}

    # Create org
    org_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Analytics Org", "category": "Спорт", "city_id": "makhachkala"},
        headers=owner_headers
    )
    org_id = org_res.json()["id"]

    # Create event
    ev_res = await client.post(
        "/api/v1/events",
        json={
            "title": "Marathon 2026",
            "description": "Annual city marathon for all athletes and enthusiasts.",
            "category_id": "sports",
            "city_id": "makhachkala",
            "start_at": "2026-12-01T08:00:00Z",
            "venue_name": "City Park",
            "address": "пр. Гамзатова, 1",
            "organization_id": org_id
        },
        headers=owner_headers
    )
    event_id = ev_res.json()["id"]

    # Publish event so views can be tracked
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Attendee 1 views and shows interest
    view_res = await client.post(f"/api/v1/events/{event_id}/view?source=discovery", headers=att_headers)
    assert view_res.status_code == 200
    int_res = await client.post(f"/api/v1/events/{event_id}/interest", headers=att_headers)
    assert int_res.status_code == 200

    # Attendee 2 RSVPs
    rsvp_res = await client.post(f"/api/v1/events/{event_id}/rsvp", headers=att2_headers)
    assert rsvp_res.status_code == 200

    # Check metrics before deletion
    insights_before = await client.get("/api/v1/organizer/insights", headers=owner_headers)
    assert insights_before.status_code == 200
    data_before = insights_before.json()
    assert data_before["events"]["total_views"] >= 1
    assert data_before["events"]["total_interest"] >= 1
    assert data_before["events"]["total_rsvps"] >= 1

    # Delete organization
    del_res = await client.delete(f"/api/v1/organizations/{org_id}", headers=owner_headers)
    assert del_res.status_code == 200

    # Event metrics after deletion
    ev_after = await client.get(f"/api/v1/events/{event_id}", headers=owner_headers)
    assert ev_after.status_code == 200
    ev_json = ev_after.json()
    assert ev_json["attendee_count"] >= 1
    assert ev_json["interest_count"] >= 1

    # Organizer insights totals STILL reflect the event engagement
    insights_after = await client.get("/api/v1/organizer/insights", headers=owner_headers)
    assert insights_after.status_code == 200
    data_after = insights_after.json()
    assert data_after["events"]["total_views"] >= 1
    assert data_after["events"]["total_interest"] >= 1
    assert data_after["events"]["total_rsvps"] >= 1


def test_frontend_confirmation_and_cancel_contract():
    """
    Verifies that OrganizerWorkspace.tsx and CreateOrganizationModal.tsx:
    1. Contain the exact confirmation modal copy ("Удалить организацию?").
    2. Contain the warning text ("Организация будет удалена. Перед удалением проверьте связанные мероприятия.").
    3. Contain "Отмена" and "Удалить организацию" buttons.
    4. Do NOT use window.confirm() or browser confirm().
    """
    workspace_path = Path("frontend/src/components/OrganizerWorkspace.tsx")
    modal_path = Path("frontend/src/components/CreateOrganizationModal.tsx")

    assert workspace_path.exists(), "OrganizerWorkspace.tsx must exist"
    assert modal_path.exists(), "CreateOrganizationModal.tsx must exist"
    workspace_text = workspace_path.read_text(encoding="utf-8")
    modal_text = modal_path.read_text(encoding="utf-8")

    combined_text = workspace_text + "\n" + modal_text

    assert "Удалить организацию?" in combined_text
    assert "Организация будет удалена. Перед удалением проверьте связанные мероприятия." in combined_text
    assert "Отмена" in combined_text
    assert "Удалить организацию" in combined_text

    # Verify no browser confirm() is used
    assert not re.search(r"\bconfirm\(", workspace_text), "Browser confirm() must not be used in OrganizerWorkspace"
    assert not re.search(r"\bconfirm\(", modal_text), "Browser confirm() must not be used in CreateOrganizationModal"


@pytest.mark.asyncio
async def test_cancel_leaves_organization_untouched(client):
    """
    When the deletion confirmation is cancelled (or delete endpoint not called),
    the organization remains untouched and fully active.
    """
    owner_init = make_test_init_data(user_id=8013, username="owner_8013")
    owner_headers = {"Authorization": f"tma {owner_init}"}

    create_res = await client.post(
        "/api/v1/organizations",
        json={"name": "Untouched Org", "category": "Кафе", "city_id": "makhachkala"},
        headers=owner_headers
    )
    org_id = create_res.json()["id"]

    # Org remains active
    get_res = await client.get(f"/api/v1/organizations/{org_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "active"
    assert get_res.json()["name"] == "Untouched Org"
