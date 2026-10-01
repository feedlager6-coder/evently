import pytest
from datetime import datetime, timezone

from app.config import settings
from app.models.organization_plan import PlanType
from app.models.broadcast import BroadcastType
from app.services.entitlement_service import EntitlementService
from tests.conftest import make_test_init_data


@pytest.mark.asyncio
async def test_transactional_broadcast_exempt_from_monthly_quota(client, test_session, monkeypatch):
    """
    1. Transactional broadcasts (operational event updates) are exempt from monthly quota:
    Even when the Free monthly quota (e.g. limit=1) is saturated with a marketing broadcast,
    an organizer can still send transactional event updates without error.
    """
    monkeypatch.setattr(settings, "FREE_BROADCASTS_PER_MONTH", 1)

    owner_id = 9301
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_trans_quota')}"}

    # Create Organization
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Exemption Theatre", "category": "Театр", "city_id": "makhachkala"},
        headers=auth,
    )
    assert res_org.status_code in (200, 201)
    org_id = res_org.json()["id"]

    # Create Event
    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Премьера Спектакля",
            "description": "Описание спектакля",
            "category_id": "concerts",
            "start_at": "2026-11-20T19:00:00Z",
            "venue_name": "Большой зал",
            "city_id": "makhachkala",
            "organization_id": org_id,
        },
        headers=auth,
    )
    assert res_ev.status_code in (200, 201)
    event_id = res_ev.json()["id"]

    from app.models.event import Event, EventStatus
    from sqlalchemy import select
    ev_db = (await test_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    ev_db.status = EventStatus.PUBLISHED.value
    await test_session.commit()

    # Add Subscriber 1
    sub_auth_1 = {"Authorization": f"tma {make_test_init_data(user_id=9401, username='sub_trans_1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth_1)

    # 1. Send Marketing broadcast (consumes quota 1 of 1)
    bcast_mkt = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
            "custom_text": "Маркетинговый анонс события",
        },
        headers=auth,
    )
    assert bcast_mkt.status_code == 200

    # Verify marketing usage is 1
    usage = await EntitlementService.get_monthly_broadcast_usage(test_session, org_id)
    assert usage == 1

    # 2. Try second marketing broadcast -> MUST fail with 403 ENTITLEMENT_REQUIRED
    sub_auth_2 = {"Authorization": f"tma {make_test_init_data(user_id=9402, username='sub_trans_2')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth_2)

    bcast_mkt_blocked = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "event_announcement",
            "event_id": event_id,
            "custom_text": "Второй анонс (должен быть заблокирован)",
        },
        headers=auth,
    )
    assert bcast_mkt_blocked.status_code == 403
    detail = bcast_mkt_blocked.json()["detail"]
    assert detail["code"] == "ENTITLEMENT_REQUIRED"
    assert "лимит бесплатных анонсов" in detail["message"]

    # 3. Send Transactional broadcast (event_update) -> MUST SUCCEED despite quota saturation!
    bcast_trans = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "transactional",
            "template_key": "event_update",
            "event_id": event_id,
            "custom_text": "Внимание! Изменение времени начала спектакля на 19:30",
        },
        headers=auth,
    )
    assert bcast_trans.status_code == 200
    assert bcast_trans.json()["broadcast_type"] == "transactional"

    # Verify marketing usage did NOT increase from transactional broadcast
    usage_after = await EntitlementService.get_monthly_broadcast_usage(test_session, org_id)
    assert usage_after == 1


@pytest.mark.asyncio
async def test_entitlement_response_humanized_copy(client, test_session):
    """
    2. Entitlements response contains humanized capability descriptions:
    Zero developer jargon (e.g. no 'атрибуция подписчиков' in public capability description).
    """
    owner_id = 9302
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_copy_check')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Copy Check Studio", "category": "Концерты", "city_id": "makhachkala"},
        headers=auth,
    )
    assert res_org.status_code in (200, 201)
    org_id = res_org.json()["id"]

    res_ent = await client.get(f"/api/v1/organizer/entitlements?org_id={org_id}", headers=auth)
    assert res_ent.status_code == 200
    data = res_ent.json()

    audience_desc = data["capabilities"]["audience_advanced"]["description"]
    assert "атрибуция" not in audience_desc.lower()
    assert "источники новых подписчиков" in audience_desc


@pytest.mark.asyncio
async def test_structured_error_format_compatibility(client, test_session, monkeypatch):
    """
    3. Structured error contains detail.message string and detail.code:
    Frontend api.ts extractErrorMessage can parse it directly without falling back to generic strings.
    """
    monkeypatch.setattr(settings, "FREE_BROADCASTS_PER_MONTH", 0)  # Immediately block marketing

    owner_id = 9303
    auth = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_err_format')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Zero Quota Place", "category": "Игры", "city_id": "makhachkala"},
        headers=auth,
    )
    assert res_org.status_code in (200, 201)
    org_id = res_org.json()["id"]

    sub_auth = {"Authorization": f"tma {make_test_init_data(user_id=9403, username='sub_zero_1')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=sub_auth)

    bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Тестовый анонс",
        },
        headers=auth,
    )
    assert bcast.status_code == 403
    payload = bcast.json()
    assert "detail" in payload
    assert isinstance(payload["detail"], dict)
    assert "message" in payload["detail"]
    assert "code" in payload["detail"]
    assert payload["detail"]["code"] == "ENTITLEMENT_REQUIRED"
    assert "тариф Pro" in payload["detail"]["message"]
