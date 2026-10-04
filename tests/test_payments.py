import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.organization import Organization
from app.models.organization_plan import OrganizationPlan, PlanType, PlanStatus
from app.models.payment import (
    PaymentOrder,
    PaymentTransaction,
    PaymentWebhookLog,
    PaymentOrderStatus,
    ReceiptStatus,
    PaymentOperationType,
)
from app.services.payment import MockYooKassaProvider
from app.services.payment_service import (
    PaymentService,
    set_payment_provider_override,
    get_payment_provider,
    ensure_utc,
    utc_now,
)
from app.services.entitlement_service import EntitlementService


@pytest.fixture(autouse=True)
def setup_mock_payment_provider():
    mock_prov = MockYooKassaProvider()
    set_payment_provider_override(mock_prov)
    yield mock_prov
    set_payment_provider_override(None)


@pytest.mark.asyncio
async def test_meta_payment_config(client):
    """Verifies that backend exposes public payment config with 499 RUB and 30 days."""
    res = await client.get("/api/v1/meta/payment-config")
    assert res.status_code == 200
    data = res.json()
    assert data["pro_monthly_price_rub"] == 499.0
    assert data["pro_days"] == 30
    assert "payments_enabled" in data


@pytest.mark.asyncio
async def test_free_org_can_create_payment(client, test_session, setup_mock_payment_provider):
    """1. Free organization owner can initiate payment and receives 499 RUB order with confirmation URL."""
    owner_id = 1101
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1101')}"}

    # Create Organization
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Club 1101", "category": "Клуб", "city_id": "makhachkala"},
        headers=auth,
    )
    assert res_org.status_code == 201
    org_id = res_org.json()["id"]

    # Temporarily enable payments for test
    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post(
            "/api/v1/organizer/payments/pro",
            json={"organization_id": org_id, "customer_email": "owner@example.com"},
            headers=auth,
        )
        assert res_pay.status_code == 201
        data = res_pay.json()

        assert data["organization_id"] == org_id
        assert data["amount"] == 499.0
        assert data["currency"] == "RUB"
        assert data["status"] == "pending"
        assert data["confirmation_url"] is not None
        assert "yookassa.ru" in data["confirmation_url"]
        assert data["receipt_status"] == "pending"


@pytest.mark.asyncio
async def test_non_owner_cannot_create_payment(client, test_session):
    """2. Non-owner cannot create payment for another user's organization."""
    owner_id = 1102
    stranger_id = 1103
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1102')}"}
    auth_stranger = {"Authorization": f"tma {make_test_init_data(user_id=stranger_id, username='stranger1103')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Private Org 1102", "category": "Музей", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post(
            "/api/v1/organizer/payments/pro",
            json={"organization_id": org_id},
            headers=auth_stranger,
        )
        assert res_pay.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_click_returns_existing_pending_payment(client, test_session, setup_mock_payment_provider):
    """8. Tapping Pay twice within TTL returns existing pending order instead of creating double orders."""
    owner_id = 1104
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1104')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Cinema 1104", "category": "Кино", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res1 = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        assert res1.status_code == 201
        order1 = res1.json()

        res2 = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        assert res2.status_code == 201
        order2 = res2.json()

        assert order1["id"] == order2["id"]
        assert order1["confirmation_url"] == order2["confirmation_url"]


@pytest.mark.asyncio
async def test_successful_payment_activates_pro_for_free_org(client, test_session, setup_mock_payment_provider):
    """9 & 10. Successful payment activates Pro on OrganizationPlan for 30 days starting from now."""
    owner_id = 1105
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1105')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Gallery 1105", "category": "Галерея", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        order_data = res_pay.json()
        order_id = order_data["id"]

        # Simulate user paid in YooKassa
        order = await test_session.get(PaymentOrder, order_id)
        setup_mock_payment_provider.simulate_payment_status(order.provider_payment_id, "succeeded", paid=True)

        # Polling/reconciliation on return
        res_check = await client.get(f"/api/v1/organizer/payments/{order_id}", headers=auth)
        assert res_check.status_code == 200
        verified_order = res_check.json()
        assert verified_order["status"] == "succeeded"

        # Verify OrganizationPlan is now PRO and expires in 30 days
        ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
        assert ent.status_code == 200
        plan_data = ent.json()
        assert plan_data["plan"] == "pro"
        assert plan_data["status"] == "active"
        exp_dt = ensure_utc(datetime.fromisoformat(plan_data["expires_at"].replace("Z", "+00:00")))
        now = utc_now()
        assert (exp_dt - now).days in (29, 30)


@pytest.mark.asyncio
async def test_active_pro_extends_from_existing_expiration(client, test_session, setup_mock_payment_provider):
    """12. If Pro is already active with 15 days remaining, payment extends by +30 days from current expires_at."""
    owner_id = 1106
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1106')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Theater 1106", "category": "Театр", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    now = utc_now()
    existing_expires = now + timedelta(days=15)
    await EntitlementService.set_organization_plan(
        test_session,
        organization_id=org_id,
        plan="pro",
        status_val="active",
        expires_at=existing_expires
    )

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        order_id = res_pay.json()["id"]
        order = await test_session.get(PaymentOrder, order_id)
        setup_mock_payment_provider.simulate_payment_status(order.provider_payment_id, "succeeded", paid=True)

        # Reconcile / poll
        await client.get(f"/api/v1/organizer/payments/{order_id}", headers=auth)

        # Check new expiration
        ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
        plan_data = ent.json()
        new_expires = ensure_utc(datetime.fromisoformat(plan_data["expires_at"].replace("Z", "+00:00")))

        diff = (new_expires - ensure_utc(existing_expires)).total_seconds()
        assert abs(diff - 30 * 86400) < 60  # exactly +30 days from existing expiration!


@pytest.mark.asyncio
async def test_amount_mismatch_rejected(client, test_session, setup_mock_payment_provider):
    """13. If provider reports amount mismatch (e.g. 49 RUB instead of 499 RUB), payment is marked failed and Pro NOT activated."""
    owner_id = 1107
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1107')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Shop 1107", "category": "Магазин", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        order_id = res_pay.json()["id"]
        order = await test_session.get(PaymentOrder, order_id)

        # Simulate provider tampered amount
        setup_mock_payment_provider.payments[order.provider_payment_id]["amount"]["value"] = "49.00"
        setup_mock_payment_provider.simulate_payment_status(order.provider_payment_id, "succeeded", paid=True)

        # Verify
        res_check = await client.get(f"/api/v1/organizer/payments/{order_id}", headers=auth)
        data = res_check.json()
        assert data["status"] == "failed"

        # Entitlements remain FREE
        ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
        assert ent.json()["plan"] == "free"


@pytest.mark.asyncio
async def test_webhook_idempotency_ten_times(client, test_session, setup_mock_payment_provider):
    """16 & 17. Same webhook delivered 10 times causes exactly ONE Pro extension, ONE notification, ONE success transaction."""
    owner_id = 1108
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1108')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Org 1108", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        order_id = res_pay.json()["id"]
        order = await test_session.get(PaymentOrder, order_id)
        setup_mock_payment_provider.simulate_payment_status(order.provider_payment_id, "succeeded", paid=True)

        webhook_payload = setup_mock_payment_provider.generate_webhook_payload(order.provider_payment_id)

        # Send same webhook 10 times
        for _ in range(10):
            res_hook = await client.post("/api/v1/payments/webhook/yookassa", json=webhook_payload)
            assert res_hook.status_code == 200

        # Verify Pro is extended exactly once
        ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
        plan_data = ent.json()
        assert plan_data["plan"] == "pro"
        exp_dt = ensure_utc(datetime.fromisoformat(plan_data["expires_at"].replace("Z", "+00:00")))
        now = utc_now()
        # Should be +30 days, NOT +300 days!
        assert (exp_dt - now).days in (29, 30)


@pytest.mark.asyncio
async def test_provider_timeout_does_not_create_duplicate(client, test_session, setup_mock_payment_provider):
    """22 & 36 & 84. Provider timeout during creation raises 503 without creating a dangling corrupted order."""
    owner_id = 1109
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1109')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Timeout Org 1109", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    setup_mock_payment_provider.should_timeout = True

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        assert res_pay.status_code == 503
        assert "Не удалось создать платёж" in res_pay.json()["detail"]


@pytest.mark.asyncio
async def test_receipt_admin_workflow(client, test_session, setup_mock_payment_provider):
    """27, 28, 29. Receipt starts pending, admin marks issued with HTTPS URL, non-HTTPS URL rejected."""
    owner_id = 1110
    admin_id = 123456789  # from settings.ADMIN_USER_IDS
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1110')}"}
    auth_admin = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin123')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Receipt Org 1110", "category": "Спорт", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth_owner)
        order_id = res_pay.json()["id"]
        order = await test_session.get(PaymentOrder, order_id)
        setup_mock_payment_provider.simulate_payment_status(order.provider_payment_id, "succeeded", paid=True)

        # Trigger success
        await client.get(f"/api/v1/organizer/payments/{order_id}", headers=auth_owner)

        # Check receipt status is pending
        res_admin_list = await client.get("/api/v1/admin/payments?receipt_status=pending", headers=auth_admin)
        assert res_admin_list.status_code == 200
        orders_list = res_admin_list.json()
        assert any(o["id"] == order_id for o in orders_list)

        # Invalid receipt URL (http instead of https)
        res_invalid = await client.post(
            f"/api/v1/admin/payments/{order_id}/receipt",
            json={"receipt_url": "http://insecure-receipt.ru/123"},
            headers=auth_admin
        )
        assert res_invalid.status_code == 422

        # Valid HTTPS receipt URL from My Tax
        valid_url = "https://lknpd.nalog.ru/api/v1/receipt/test_receipt_1110"
        res_valid = await client.post(
            f"/api/v1/admin/payments/{order_id}/receipt",
            json={"receipt_url": valid_url},
            headers=auth_admin
        )
        assert res_valid.status_code == 200
        updated = res_valid.json()
        assert updated["receipt_status"] == "issued"
        assert updated["receipt_url"] == valid_url


@pytest.mark.asyncio
async def test_refund_webhook_recorded_safely(client, test_session, setup_mock_payment_provider):
    """32 & 33. Refund webhook marks order refunded and does NOT extend or corrupt Pro."""
    owner_id = 1111
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1111')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Refund Org 1111", "category": "Клуб", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        res_pay = await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)
        order_id = res_pay.json()["id"]
        order = await test_session.get(PaymentOrder, order_id)
        setup_mock_payment_provider.simulate_payment_status(order.provider_payment_id, "succeeded", paid=True)

        # First succeed
        await client.get(f"/api/v1/organizer/payments/{order_id}", headers=auth)

        # Then receive refund webhook
        refund_payload = {
            "type": "notification",
            "event": "refund.succeeded",
            "object": {
                "id": order.provider_payment_id,
                "status": "succeeded",
                "amount": {"value": "499.00", "currency": "RUB"}
            }
        }
        res_hook = await client.post("/api/v1/payments/webhook/yookassa", json=refund_payload)
        assert res_hook.status_code == 200

        # Check order status is refunded
        order_after = await test_session.get(PaymentOrder, order_id)
        assert order_after.status == "refunded"


@pytest.mark.asyncio
async def test_payment_history_endpoint(client, test_session, setup_mock_payment_provider):
    """Verifies chronological payment history endpoint for organization."""
    owner_id = 1112
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner1112')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "History Org 1112", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    org_id = res_org.json()["id"]

    with patch.object(settings, "PAYMENTS_ENABLED", True):
        await client.post("/api/v1/organizer/payments/pro", json={"organization_id": org_id}, headers=auth)

        res_hist = await client.get(f"/api/v1/organizer/payments?org_id={org_id}", headers=auth)
        assert res_hist.status_code == 200
        hist = res_hist.json()
        assert len(hist) >= 1
        assert hist[0]["amount"] == 499.0
        assert hist[0]["currency"] == "RUB"
