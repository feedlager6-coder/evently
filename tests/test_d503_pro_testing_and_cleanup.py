import pytest
import os
from unittest.mock import patch
from tests.conftest import make_test_init_data
from app.config import settings
from app.services.notification_service import resolve_event_cover_url


@pytest.mark.asyncio
async def test_d503_01_free_org_broadcast_rejected(client, test_session):
    """1. Free organization cannot create marketing broadcast: 403 ENTITLEMENT_REQUIRED."""
    user_id = 9101
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='free_org_owner')}"}

    # Create organization (defaults to Free)
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "D503 Free Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth,
    )
    assert res_org.status_code in (200, 201)
    org_id = res_org.json()["id"]

    # Subscribe a user so audience is non-zero
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9102, username='sub_d503_1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    # Attempt to broadcast
    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Free org attempting broadcast",
        },
        headers=auth,
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["code"] == "ENTITLEMENT_REQUIRED"
    assert detail["capability"] == "broadcasts_extended"
    assert detail["required_plan"] == "pro"


@pytest.mark.asyncio
async def test_d503_02_pro_org_broadcast_allowed_and_quota_tracked(client, test_session):
    """2. Pro organization can create broadcast and monthly quota is tracked (up to 30)."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_d503')}"}
    user_id = 9201
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='pro_org_owner')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "D503 Pro Org", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    # Admin sets org to Pro
    res_plan = await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "status": "active"},
        headers=admin_auth,
    )
    assert res_plan.status_code == 200
    assert res_plan.json()["plan"] == "pro"
    assert res_plan.json()["capabilities"]["broadcasts_extended"]["status"] == "available"

    # Subscribe a user
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9202, username='sub_d503_2')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Pro org broadcasting announcement",
        },
        headers=auth,
    )
    assert res.status_code in (200, 201)
    b_data = res.json()
    assert b_data["status"] in ("pending", "processing", "sent", "completed")

    # Inspect entitlements quota consumption
    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent.status_code == 200
    ent = res_ent.json()
    assert ent["limits"]["broadcasts_used_this_month"] == 1
    assert ent["limits"]["broadcasts_remaining"] == 29
    assert ent["limits"]["broadcasts_per_month"] == 30


@pytest.mark.asyncio
async def test_d503_03_admin_user_without_pro_org_cannot_broadcast(client, test_session):
    """3. Admin user without Pro org remains Free: admin role != commercial Pro entitlement."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_user')}"}

    # Admin creates an organization
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Admin Free Org", "category": "Спорт", "city_id": "makhachkala"},
        headers=admin_auth,
    )
    org_id = res_org.json()["id"]

    # Subscribe user
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9301, username='sub_admin_1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    # Admin checks entitlements for this org -> should be 'free'
    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=admin_auth)
    assert res_ent.status_code == 200
    assert res_ent.json()["plan"] == "free"
    assert res_ent.json()["capabilities"]["broadcasts_extended"]["status"] == "locked"

    # Attempt to broadcast -> 403 ENTITLEMENT_REQUIRED
    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Admin attempting broadcast without Pro plan",
        },
        headers=admin_auth,
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ENTITLEMENT_REQUIRED"


@pytest.mark.asyncio
async def test_d503_04_admin_can_activate_pro_via_admin_api(client, test_session):
    """4. Admin user can explicitly activate Pro on an organization and then broadcast successfully."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_activator')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Org To Promote", "category": "Театр", "city_id": "makhachkala"},
        headers=admin_auth,
    )
    org_id = res_org.json()["id"]

    # Activate Pro via admin API
    res_promote = await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "status": "active"},
        headers=admin_auth,
    )
    assert res_promote.status_code == 200
    assert res_promote.json()["plan"] == "pro"
    assert res_promote.json()["capabilities"]["broadcasts_extended"]["status"] == "available"

    # Subscribe user
    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9401, username='sub_promoted')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    # Now broadcast succeeds!
    res_b = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Announcement after admin Pro activation",
        },
        headers=admin_auth,
    )
    assert res_b.status_code in (200, 201)


@pytest.mark.asyncio
async def test_d503_05_admin_can_revert_org_to_free(client, test_session):
    """5. Admin can revert Pro organization back to Free, blocking broadcasts again."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_toggle')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Org Revertible", "category": "Кино", "city_id": "makhachkala"},
        headers=admin_auth,
    )
    org_id = res_org.json()["id"]

    # Set to Pro
    await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "status": "active"},
        headers=admin_auth,
    )

    # Revert to Free
    res_revert = await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "free", "status": "active"},
        headers=admin_auth,
    )
    assert res_revert.status_code == 200
    assert res_revert.json()["plan"] == "free"
    assert res_revert.json()["capabilities"]["broadcasts_extended"]["status"] == "locked"

    # Attempt to broadcast -> 403
    res_b = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Blocked after reverting to Free",
        },
        headers=admin_auth,
    )
    assert res_b.status_code == 403
    assert res_b.json()["detail"]["code"] == "ENTITLEMENT_REQUIRED"


@pytest.mark.asyncio
async def test_d503_06_non_admin_cannot_access_admin_plan_or_list(client, test_session):
    """6. Non-admin users are strictly denied (HTTP 403) from admin plan & organization endpoints."""
    regular_user_id = 888111
    auth = {"Authorization": f"tma {make_test_init_data(user_id=regular_user_id, username='regular_user')}"}

    # Attempt GET /api/v1/admin/organizations
    res1 = await client.get("/api/v1/admin/organizations", headers=auth)
    assert res1.status_code == 403

    # Attempt POST /api/v1/admin/organizations/{id}/plan
    res2 = await client.post(
        "/api/v1/admin/organizations/any-org-id/plan",
        json={"plan": "pro"},
        headers=auth,
    )
    assert res2.status_code == 403

    # Attempt GET /api/v1/admin/organizations/{id}/entitlements
    res3 = await client.get("/api/v1/admin/organizations/any-org-id/entitlements", headers=auth)
    assert res3.status_code == 403


@pytest.mark.asyncio
async def test_d503_07_admin_can_list_organizations(client, test_session):
    """7. Admin can list all active organizations with their plan and owner information."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_lister')}"}
    user_id = 777222
    user_auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='creator_user')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Org Listed", "category": "Музеи", "city_id": "makhachkala"},
        headers=user_auth,
    )
    org_id = res_org.json()["id"]

    res_list = await client.get("/api/v1/admin/organizations", headers=admin_auth)
    assert res_list.status_code == 200
    orgs = res_list.json()
    assert isinstance(orgs, list)
    target = next((o for o in orgs if o["id"] == org_id), None)
    assert target is not None
    assert target["name"] == "Org Listed"
    assert target["category"] == "Музеи"
    assert target["owner_user_id"] > 0
    assert target["plan"] == "free"
    assert target["status"] == "active"


@pytest.mark.asyncio
async def test_d503_08_admin_endpoints_nonexistent_org_404(client, test_session):
    """8. Admin endpoints return 404 for nonexistent or deleted organizations."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_tester')}"}

    res_plan = await client.post(
        "/api/v1/admin/organizations/nonexistent-org-0000/plan",
        json={"plan": "pro"},
        headers=admin_auth,
    )
    assert res_plan.status_code == 404
    assert "не найдена" in res_plan.json()["detail"].lower()

    res_ent = await client.get(
        "/api/v1/admin/organizations/nonexistent-org-0000/entitlements",
        headers=admin_auth,
    )
    assert res_ent.status_code == 404
    assert "не найдена" in res_ent.json()["detail"].lower()


@pytest.mark.asyncio
async def test_d503_09_non_owner_cannot_inspect_other_org_entitlements(client, test_session):
    """9. Non-owner cannot view another user's organization entitlements via organizer API (403)."""
    owner_id = 666111
    owner_auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_d503')}"}
    other_id = 666222
    other_auth = {"Authorization": f"tma {make_test_init_data(user_id=other_id, username='other_d503')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Owner Org", "category": "Лекции", "city_id": "makhachkala"},
        headers=owner_auth,
    )
    org_id = res_org.json()["id"]

    res = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=other_auth)
    assert res.status_code == 403
    assert "владельцем" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_d503_10_manual_transactional_broadcast_rejected_400(client, test_session):
    """10. Manual transactional broadcast creation is rejected with HTTP 400 Bad Request."""
    admin_id = 123456789
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_tx_test')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Tx Test Org", "category": "Конференции", "city_id": "makhachkala"},
        headers=admin_auth,
    )
    org_id = res_org.json()["id"]

    # Even on Pro, transactional cannot be manually created
    await client.post(
        f"/api/v1/admin/organizations/{org_id}/plan",
        json={"plan": "pro", "status": "active"},
        headers=admin_auth,
    )

    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "transactional",
            "template_key": "event_cancelled",
            "custom_text": "Attempting manual transactional",
        },
        headers=admin_auth,
    )
    assert res.status_code == 400
    assert "сервисные уведомления" in res.json()["detail"].lower()


def test_d503_11_public_host_settings_and_cover_url_resolution():
    """11. Public host settings priority and resolve_event_cover_url formatting."""
    # Test APP_PUBLIC_HOST precedence
    with patch.object(settings, "APP_PUBLIC_HOST", "https://ivently.up.railway.app"), \
         patch.object(settings, "PUBLIC_HOST", "https://other.domain.com"):
        assert settings.effective_public_host == "https://ivently.up.railway.app"

    # Test fallback to PUBLIC_HOST
    with patch.object(settings, "APP_PUBLIC_HOST", None), \
         patch.object(settings, "PUBLIC_HOST", "https://public.domain.com"):
        assert settings.effective_public_host == "https://public.domain.com"

    # Test production fallback
    with patch.object(settings, "APP_PUBLIC_HOST", None), \
         patch.object(settings, "PUBLIC_HOST", None), \
         patch.dict(os.environ, {}, clear=True), \
         patch.object(settings, "APP_ENV", "production"):
        assert settings.effective_public_host == "https://ivently.up.railway.app"

    # Test resolve_event_cover_url with effective_public_host
    with patch.object(settings, "APP_PUBLIC_HOST", "https://ivently.up.railway.app"):
        resolved = resolve_event_cover_url("/uploads/events/cover123.jpg")
        assert resolved == "https://ivently.up.railway.app/uploads/events/cover123.jpg"

        # Already full url remains untouched
        assert resolve_event_cover_url("https://cdn.example.com/pic.jpg") == "https://cdn.example.com/pic.jpg"
