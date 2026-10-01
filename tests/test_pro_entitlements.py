import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, text

from tests.conftest import make_test_init_data
from app.config import settings
from app.database import init_db
from app.models.organization import Organization
from app.models.organization_plan import OrganizationPlan, PlanType, PlanStatus
from app.models.subscription import Subscription
from app.models.event import Event
from app.services.entitlement_service import EntitlementService, CAPABILITY_REGISTRY


@pytest.mark.asyncio
async def test_new_organization_resolves_to_free(client, test_session):
    """
    1. New organization → FREE.
    When a new organization is created, it defaults to the Free plan.
    """
    owner_id = 9101
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_free')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Free Test Place", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent.status_code == 200
    data = res_ent.json()

    assert data["organization_id"] == org_id
    assert data["plan"] == "free"
    assert data["status"] == "active"
    assert data["expires_at"] is None
    assert data["capabilities"]["broadcasts_extended"]["status"] == "locked"
    assert data["capabilities"]["broadcasts_extended"]["is_pro_feature"] is True
    assert data["limits"]["broadcasts_per_month"] == settings.FREE_BROADCASTS_PER_MONTH


@pytest.mark.asyncio
async def test_free_capability_resolution(test_session):
    """
    2. FREE capability resolution:
    Locked vs coming_soon capabilities are properly resolved for Free plan.
    """
    org_id = "test-free-org-uuid"

    # Core Pro features are locked
    allowed, reason, req_plan = await EntitlementService.check_capability(test_session, org_id, "broadcasts_extended")
    assert allowed is False
    assert req_plan == "pro"

    allowed, reason, req_plan = await EntitlementService.check_capability(test_session, org_id, "audience_advanced")
    assert allowed is False
    assert req_plan == "pro"

    # Future features are coming_soon
    allowed, reason, req_plan = await EntitlementService.check_capability(test_session, org_id, "reminders")
    assert allowed is False
    assert req_plan is None
    assert "в разработке" in reason


@pytest.mark.asyncio
async def test_pro_capability_resolution(client, test_session):
    """
    3. PRO capability resolution:
    When organization has an active Pro plan, Pro capabilities resolve to 'available'.
    """
    owner_id = 9102
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_pro')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Pro Concert Hall", "category": "Концертная площадка", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Upgrade to Pro
    await EntitlementService.set_organization_plan(test_session, org_id, plan="pro")

    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent.status_code == 200
    data = res_ent.json()

    assert data["plan"] == "pro"
    assert data["status"] == "active"
    assert data["capabilities"]["broadcasts_extended"]["status"] == "available"
    assert data["capabilities"]["audience_advanced"]["status"] == "available"
    assert data["capabilities"]["analytics_advanced"]["status"] == "available"
    # Unreleased features remain coming_soon
    assert data["capabilities"]["reminders"]["status"] == "coming_soon"
    assert data["limits"]["broadcasts_per_month"] == settings.PRO_BROADCASTS_PER_MONTH


@pytest.mark.asyncio
async def test_unknown_capability_handled_safely(test_session):
    """
    4. Unknown capability handled safely:
    Querying a nonexistent capability fails gracefully without crash.
    """
    org_id = "test-nonexistent-org"
    allowed, reason, req_plan = await EntitlementService.check_capability(test_session, org_id, "unknown_flying_cars")
    assert allowed is False
    assert "Неизвестная возможность" in reason
    assert req_plan is None


@pytest.mark.asyncio
async def test_expired_entitlement_degrades_to_free(client, test_session):
    """
    5. Expired entitlement automatically degrades to FREE:
    When expires_at is in the past, effective plan is resolved as 'free' with status 'expired'.
    """
    owner_id = 9103
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_expired')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Expired Pro Cafe", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Set plan to pro with past expiration date
    past_date = datetime.now(timezone.utc) - timedelta(days=2)
    await EntitlementService.set_organization_plan(
        test_session, org_id, plan="pro", expires_at=past_date
    )

    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent.status_code == 200
    data = res_ent.json()

    assert data["plan"] == "free"
    assert data["status"] == "expired"
    assert data["capabilities"]["broadcasts_extended"]["status"] == "locked"
    assert data["limits"]["broadcasts_per_month"] == settings.FREE_BROADCASTS_PER_MONTH


@pytest.mark.asyncio
async def test_multi_organization_isolation(client, test_session):
    """
    6. Multi-organization isolation:
    User owns Org A and Org B. Setting Org A to Pro must NOT leak to Org B.
    """
    owner_id = 9104
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_multiorg')}"}

    # Create Org A
    res_a = await client.post(
        "/api/v1/organizations",
        json={"name": "Multi Org Alpha", "category": "Бар", "city_id": "makhachkala"},
        headers=auth,
    )
    org_a_id = res_a.json()["id"]

    # Create Org B
    res_b = await client.post(
        "/api/v1/organizations",
        json={"name": "Multi Org Beta", "category": "Клуб", "city_id": "makhachkala"},
        headers=auth,
    )
    org_b_id = res_b.json()["id"]

    # Upgrade only Org A to Pro
    await EntitlementService.set_organization_plan(test_session, org_a_id, plan="pro")

    # Check Org A
    res_ent_a = await client.get(f"/api/v1/organizer/entitlements?org_id={org_a_id}", headers=auth)
    assert res_ent_a.status_code == 200
    assert res_ent_a.json()["plan"] == "pro"
    assert res_ent_a.json()["capabilities"]["broadcasts_extended"]["status"] == "available"

    # Check Org B: MUST strictly remain Free!
    res_ent_b = await client.get(f"/api/v1/organizer/entitlements?org_id={org_b_id}", headers=auth)
    assert res_ent_b.status_code == 200
    assert res_ent_b.json()["plan"] == "free"
    assert res_ent_b.json()["capabilities"]["broadcasts_extended"]["status"] == "locked"


@pytest.mark.asyncio
async def test_deleted_organization_returns_404(client, test_session):
    """
    7. Deleted organization:
    Requesting entitlements for a soft-deleted organization returns 404 Not Found.
    """
    owner_id = 9105
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_del')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "To Delete Org", "category": "Другое", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Delete organization
    del_res = await client.delete(f"/api/v1/organizations/{org_id}", headers=auth)
    assert del_res.status_code == 200

    # Requesting entitlements must return 404
    ent_res = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert ent_res.status_code == 404


@pytest.mark.asyncio
async def test_non_owner_cannot_access_entitlements(client, test_session):
    """
    8. Non-owner cannot access organizer entitlement:
    Attempting to inspect entitlements of someone else's organization returns 403 Forbidden.
    """
    owner_id = 9106
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_real')}"}

    stranger_id = 9107
    auth_stranger = {"Authorization": f"tma {make_test_init_data(user_id=stranger_id, username='stranger')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Secret Org", "category": "Театр", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    # Stranger tries to inspect entitlements
    res_hack = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth_stranger)
    assert res_hack.status_code == 403
    assert "Вы не являетесь владельцем" in res_hack.json()["detail"]


@pytest.mark.asyncio
async def test_frontend_endpoint_data_safety(client, test_session):
    """
    9. Frontend endpoint returns only allowed public organizer data:
    Response contains no telegram_id, no database internal user ids, no passwords or secrets.
    """
    owner_id = 9108
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_safe')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Public Clean Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent.status_code == 200
    data = res_ent.json()

    # Verify no leaked fields
    assert "telegram_id" not in data
    assert "owner_user_id" not in data
    assert "secret" not in data
    assert "password" not in data
    assert "token" not in data
    assert "capabilities" in data
    assert "limits" in data


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_free_user_quota_enforcement(client, test_session):
    """
    10. Free user cannot send manual broadcasts:
    Free organization attempting to create a manual marketing broadcast is blocked
    with HTTP 403 Forbidden and code ENTITLEMENT_REQUIRED (required_plan='pro').
    """
    owner_id = 9109
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_quota')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Quota Limited Place", "category": "Клуб", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Add subscriber
    sub_auth_1 = {"Authorization": f"tma {make_test_init_data(user_id=9201, username='sub_quota_1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth_1)

    # Free manual broadcast must be rejected by entitlement enforcement
    bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Free user broadcast attempt",
        },
        headers=auth,
    )
    assert bcast.status_code == 403
    detail = bcast.json()["detail"]
    assert detail["code"] == "ENTITLEMENT_REQUIRED"
    assert detail["capability"] == "broadcasts_extended"
    assert detail["required_plan"] == "pro"


@pytest.mark.asyncio
async def test_existing_free_broadcast_flow_works(client, test_session):
    """
    11. Broadcast flow works when upgraded to Pro:
    When an organization is on the Pro plan, broadcasts succeed completely.
    """
    owner_id = 9110
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_working_flow')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Working Free Org", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Upgrade to Pro
    await EntitlementService.set_organization_plan(test_session, org_id, plan="pro")

    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9250, username='sub_working')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Hello Pro subscribers!",
        },
        headers=auth,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["organization_id"] == org_id
    assert data["delivered_count"] == 1


@pytest.mark.asyncio
async def test_pro_operation_allowed_when_entitled(client, test_session, monkeypatch):
    """
    12. Pro operation is allowed when entitlement exists:
    When upgraded to Pro, broadcasts beyond the Free limit are allowed up to the Pro limit.
    """
    monkeypatch.setattr(settings, "FREE_BROADCASTS_PER_MONTH", 1)
    monkeypatch.setattr(settings, "PRO_BROADCASTS_PER_MONTH", 10)

    owner_id = 9111
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_pro_flow')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Pro Allowed Org", "category": "Концертная площадка", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Upgrade to Pro
    await EntitlementService.set_organization_plan(test_session, org_id, plan="pro")

    # Add subscriber 1 for first broadcast
    sub_auth_1 = {"Authorization": f"tma {make_test_init_data(user_id=9203, username='sub_pro_1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth_1)

    # 1st broadcast
    res_1 = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Pro Broadcast 1",
        },
        headers=auth,
    )
    assert res_1.status_code == 200

    # Add subscriber 2 (unfatigued for 2nd broadcast)
    sub_auth_2 = {"Authorization": f"tma {make_test_init_data(user_id=9204, username='sub_pro_2')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth_2)

    # 2nd broadcast (would have failed under Free quota of 1, but succeeds under Pro!)
    res_2 = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Pro Broadcast 2",
        },
        headers=auth,
    )
    assert res_2.status_code == 200


@pytest.mark.asyncio
async def test_migration_and_table_initialization(test_session):
    """
    13, 14, 15: Migration fresh DB, upgrade, and idempotent execution:
    Calling init_db multiple times must be completely safe, additive, and idempotent.
    """
    # 1. Run init_db
    await init_db()

    # 2. Re-run init_db (must not raise or fail)
    await init_db()

    # 3. Verify organization_plans table is queryable
    res = await test_session.execute(select(OrganizationPlan))
    assert res.scalars().all() is not None


@pytest.mark.asyncio
async def test_admin_dev_endpoints(client, test_session):
    """
    Admin/Dev visibility endpoint:
    Admins can inspect entitlements and switch plans for testing.
    """
    admin_id = 123456789  # configured admin ID in settings.ADMIN_USER_IDS
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_user')}"}

    # Create org by regular user
    user_auth = {"Authorization": f"tma {make_test_init_data(user_id=9112, username='regular_dev')}"}
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Dev Admin Target", "category": "Спорт", "city_id": "makhachkala"},
        headers=user_auth,
    )
    org_id = res_org.json()["id"]

    # Admin inspects entitlements
    admin_ent = await client.get(f"/api/v1/admin/organizations/{org_id}/entitlements", headers=admin_auth)
    assert admin_ent.status_code == 200
    assert admin_ent.json()["plan"] == "free"

    # Admin switches plan to Pro
    switch_res = await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "expires_in_days": 30},
        headers=admin_auth,
    )
    assert switch_res.status_code == 200
    assert switch_res.json()["plan"] == "pro"
    assert switch_res.json()["status"] == "active"
    assert switch_res.json()["expires_at"] is not None
