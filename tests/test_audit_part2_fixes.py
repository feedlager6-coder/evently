import uuid
import httpx
import pytest
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_plan import OrganizationPlan, PlanType, PlanStatus
from app.models.attendee import EventAttendee
from app.models.ticket_checkin import TicketCheckIn
from app.models.city import City
from app.models.payment import PaymentOrder, PaymentOrderStatus
from app.models.broadcast import Broadcast, BroadcastTargetType, BroadcastType, BroadcastTemplateKey
from app.models.subscription import Subscription
from app.services.event_service import compute_ticket_signature, build_signed_ticket_code
from app.services.payment_service import PaymentService, set_payment_provider_override
from app.services.payment.mock_provider import MockYooKassaProvider
from app.services.organization_service import list_user_subscriptions
from app.services.broadcast_service import (
    calculate_audience,
    create_broadcast,
    dispatch_broadcast,
    format_broadcast_date_str,
)


@pytest.mark.asyncio
async def test_ticket_signature_hmac_and_checkin_validation(client, test_session, monkeypatch):
    """
    Block 1: Cryptographic Ticket Protection (HMAC-SHA256)
    - Valid 4-part signature passes check-in.
    - Tampered signature is rejected with status="invalid".
    - Missing signature is rejected in production (APP_ENV=production).
    - Double check-in returns status="already_checked_in".
    - Non-attendee check-in returns status="invalid".
    """
    organizer_id = 911001
    org_auth = {"Authorization": f"tma {make_test_init_data(user_id=organizer_id, username='sig_host')}"}

    host_user = User(id=organizer_id, telegram_id=organizer_id, username="sig_host")
    test_session.add(host_user)

    event = Event(
        title="HMAC Security Fest",
        description="Testing ticket crypto signature",
        category_id="parties",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Crypto Stage",
        address="Dagestanskaya 1",
        organizer_user_id=organizer_id,
        status=EventStatus.PUBLISHED.value,
        price_amount=0,
    )
    test_session.add(event)
    await test_session.commit()

    guest_user_id = 911002
    guest_user = User(id=guest_user_id, telegram_id=guest_user_id, username="legit_guest", first_name="Тимур")
    test_session.add(guest_user)
    await test_session.commit()

    # Register guest as attendee
    attendee = EventAttendee(event_id=event.id, user_id=guest_user.id)
    test_session.add(attendee)
    await test_session.commit()

    # 1. Valid signed ticket code
    valid_ticket_code = build_signed_ticket_code(event.id, guest_user.id)
    expected_sig = compute_ticket_signature(event.id, guest_user.id)
    assert expected_sig in valid_ticket_code

    # 2. Tampered signature -> REJECTED
    tampered_code = valid_ticket_code[:-2] + ("00" if valid_ticket_code[-2:] != "00" else "FF")
    resp_tampered = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": tampered_code}
    )
    assert resp_tampered.status_code == 200
    data_tampered = resp_tampered.json()
    assert data_tampered["status"] == "invalid"
    assert "подпис" in data_tampered["message"].lower()

    # 3. Missing signature in production -> REJECTED
    monkeypatch.setattr(settings, "APP_ENV", "production")
    legacy_code = f"IVN-{str(event.id).replace('-', '')[:4].upper()}-{guest_user.id}"
    resp_prod_legacy = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": legacy_code}
    )
    assert resp_prod_legacy.status_code == 200
    assert resp_prod_legacy.json()["status"] == "invalid"
    assert "подпис" in resp_prod_legacy.json()["message"].lower()

    # Restore dev mode
    monkeypatch.setattr(settings, "APP_ENV", "development")

    # 4. Valid check-in -> SUCCESS
    resp_valid = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": valid_ticket_code}
    )
    assert resp_valid.status_code == 200
    data_valid = resp_valid.json()
    assert data_valid["status"] == "success"
    assert data_valid["guest_name"] == "Тимур"

    # Verify persistent TicketCheckIn created
    checkin_stmt = select(TicketCheckIn).where(TicketCheckIn.event_id == event.id)
    checkin = (await test_session.execute(checkin_stmt)).scalars().first()
    assert checkin is not None

    # 5. Double check-in -> ALREADY_CHECKED_IN
    resp_repeat = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": valid_ticket_code}
    )
    assert resp_repeat.status_code == 200
    assert resp_repeat.json()["status"] == "already_checked_in"

    # 6. Non-attendee with mathematically valid signature for another user -> INVALID
    other_user_id = 911003
    other_user = User(id=other_user_id, telegram_id=other_user_id, username="unregistered_guest")
    test_session.add(other_user)
    await test_session.commit()

    other_valid_sig_code = build_signed_ticket_code(event.id, other_user.id)
    resp_other = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": other_valid_sig_code}
    )
    assert resp_other.status_code == 200
    assert resp_other.json()["status"] == "invalid"
    assert "не найден среди регистраций" in resp_other.json()["message"].lower()


@pytest.mark.asyncio
async def test_yookassa_webhook_cancellation_and_refund_revocation(client, test_session):
    """
    Block 2: Payment Webhook Verification and Plan Revocation
    - payment.canceled: verified with provider -> order marked CANCELLED.
    - refund.succeeded: verified with provider -> order marked REFUNDED and OrganizationPlan revoked.
    - order.expires_at is populated on plan activation.
    """
    user_id = 912001
    user = User(id=user_id, telegram_id=user_id, username="yoo_subscriber")
    test_session.add(user)
    await test_session.commit()

    org = Organization(
        name="Pro Agency",
        slug="pro-agency-webhook-test",
        category="concerts",
        city_id="makhachkala",
        owner_user_id=user.id,
        status=OrganizationStatus.ACTIVE.value,
    )
    test_session.add(org)
    await test_session.commit()

    mock_prov = MockYooKassaProvider()
    set_payment_provider_override(mock_prov)
    try:
        # 1. Test payment.canceled webhook verification
        order_cancel = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            organization_id=org.id,
            amount=1990.00,
            currency="RUB",
            provider="yookassa",
            provider_payment_id="yoo_pay_cancel_123",
            idempotency_key=str(uuid.uuid4()),
            status=PaymentOrderStatus.PENDING.value,
        )
        test_session.add(order_cancel)
        await test_session.commit()

        # Seed mock provider with canceled payment state
        mock_prov.payments["yoo_pay_cancel_123"] = {
            "id": "yoo_pay_cancel_123",
            "status": "canceled",
            "paid": False,
            "amount": {"value": "1990.00", "currency": "RUB"},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {},
        }

        # Webhook with payment.canceled
        cancel_payload = {
            "event": "payment.canceled",
            "object": {
                "id": "yoo_pay_cancel_123",
                "status": "canceled",
                "cancellation_details": {"party": "yoo_kassa", "reason": "expired_on_confirmation"},
            }
        }
        resp_cancel = await client.post("/api/v1/payments/webhook/yookassa", json=cancel_payload)
        assert resp_cancel.status_code == 200
        assert resp_cancel.json()["ok"] is True

        await test_session.refresh(order_cancel)
        assert order_cancel.status == PaymentOrderStatus.CANCELED.value

        # 2. Test refund.succeeded webhook and PRO revocation
        # First activate PRO plan
        plan_record = OrganizationPlan(
            organization_id=org.id,
            plan=PlanType.PRO.value,
            status=PlanStatus.ACTIVE.value,
            starts_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        test_session.add(plan_record)

        order_refund = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            organization_id=org.id,
            amount=1990.00,
            currency="RUB",
            provider="yookassa",
            provider_payment_id="yoo_pay_refund_456",
            idempotency_key=str(uuid.uuid4()),
            status=PaymentOrderStatus.SUCCEEDED.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        test_session.add(order_refund)
        await test_session.commit()

        # Seed mock provider with refunded payment state
        mock_prov.payments["yoo_pay_refund_456"] = {
            "id": "yoo_pay_refund_456",
            "status": "canceled",
            "paid": True,
            "amount": {"value": "1990.00", "currency": "RUB"},
            "refunded_amount": {"value": "1990.00", "currency": "RUB"},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {},
        }

        refund_payload = {
            "event": "refund.succeeded",
            "object": {
                "id": "yoo_refund_456",
                "payment_id": "yoo_pay_refund_456",
                "status": "succeeded",
            }
        }
        resp_refund = await client.post("/api/v1/payments/webhook/yookassa", json=refund_payload)
        assert resp_refund.status_code == 200
        assert resp_refund.json()["ok"] is True

        await test_session.refresh(order_refund)
        assert order_refund.status == PaymentOrderStatus.REFUNDED.value

        await test_session.refresh(plan_record)
        assert plan_record.plan == PlanType.FREE.value
        assert plan_record.status == PlanStatus.CANCELLED.value
    finally:
        set_payment_provider_override(None)


@pytest.mark.asyncio
async def test_silent_broadcast_and_notification_flag(client, test_session, monkeypatch):
    """
    Block 2: Silent Broadcast
    - is_silent parameter is saved on Broadcast model.
    - disable_notification is propagated to Telegram delivery.
    """
    user_id = 913001
    auth_header = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='silent_sender')}"}
    user = User(id=user_id, telegram_id=user_id, username="silent_sender")
    test_session.add(user)

    org = Organization(
        name="Silent Sounds",
        slug="silent-sounds-test",
        category="music",
        city_id="makhachkala",
        owner_user_id=user_id,
        status=OrganizationStatus.ACTIVE.value,
    )
    test_session.add(org)
    await test_session.commit()

    # Activate PRO plan so quota allows broadcast
    plan = OrganizationPlan(
        organization_id=org.id,
        plan=PlanType.PRO.value,
        status=PlanStatus.ACTIVE.value,
        starts_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    test_session.add(plan)
    await test_session.commit()

    # Subscriber with active notifications
    sub_user = User(id=913002, telegram_id=913002, username="sub_recipient")
    test_session.add(sub_user)
    sub = Subscription(organization_id=org.id, user_id=sub_user.id, notifications_enabled=True)
    test_session.add(sub)
    await test_session.commit()

    resp = await client.post(
        "/api/v1/organizer/broadcasts",
        headers=auth_header,
        json={
            "organization_id": org.id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Тихое ночное обновление без звука",
            "is_silent": True,
        }
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["is_silent"] is True

    bcast_id = data["id"]
    bcast_db = (await test_session.execute(select(Broadcast).where(Broadcast.id == bcast_id))).scalar_one()
    assert bcast_db.is_silent is True

    # Test delivery engine passes disable_notification=True to Telegram
    from app.models.broadcast import BroadcastRecipient, RecipientStatus, BroadcastStatus
    bcast_db.status = BroadcastStatus.QUEUED.value
    recs = (await test_session.execute(select(BroadcastRecipient).where(BroadcastRecipient.broadcast_id == bcast_id))).scalars().all()
    for r in recs:
        r.status = RecipientStatus.PENDING.value
    await test_session.commit()

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 999111}}
    mock_http.post.return_value = mock_resp

    await dispatch_broadcast(test_session, bcast_id, http_client=mock_http)
    mock_http.post.assert_awaited()
    call_kwargs = mock_http.post.call_args.kwargs
    sent_payload = call_kwargs.get("json") or call_kwargs.get("data")
    assert sent_payload.get("disable_notification") is True


@pytest.mark.asyncio
async def test_timezone_formatting_city_local_datetime(test_session):
    """
    Block 2: Timezone localization for broadcasts and events
    - Correctly calculates local time in Vladivostok (UTC+10).
    """
    vl_city = (await test_session.execute(select(City).where(City.id == "vladivostok"))).scalar_one_or_none()
    if not vl_city:
        vl_city = City(id="vladivostok", name="Владивосток", country="Россия", currency="RUB", timezone="Asia/Vladivostok")
        test_session.add(vl_city)
        await test_session.commit()

    event_vl = Event(
        title="Тихоокеанский Закат",
        description="Закат над Амурским заливом",
        address="Набережная 1",
        category_id="parties",
        city_id=vl_city.id,
        city=vl_city,
        start_at=datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc),  # 09:00 UTC -> 19:00 in Vladivostok (UTC+10)
        venue_name="Набережная",
        organizer_user_id=1,
        status=EventStatus.PUBLISHED.value,
    )
    test_session.add(event_vl)
    await test_session.commit()

    date_str = format_broadcast_date_str(event_vl)
    assert "19:00" in date_str
    assert "15" in date_str


@pytest.mark.asyncio
async def test_n_plus_one_elimination_in_list_user_subscriptions(test_session):
    """
    Block 2: N+1 query elimination and unambiguous correlation in list_user_subscriptions
    """
    u = User(id=914001, telegram_id=914001, username="sub_browser")
    test_session.add(u)

    org1 = Organization(
        name="Org A",
        slug="org-a-n1-test",
        category="concerts",
        city_id="makhachkala",
        owner_user_id=u.id,
        status=OrganizationStatus.ACTIVE.value,
    )
    org2 = Organization(
        name="Org B",
        slug="org-b-n1-test",
        category="parties",
        city_id="makhachkala",
        owner_user_id=u.id,
        status=OrganizationStatus.ACTIVE.value,
    )
    test_session.add_all([org1, org2])
    await test_session.commit()

    sub1 = Subscription(organization_id=org1.id, user_id=u.id, notifications_enabled=True)
    sub2 = Subscription(organization_id=org2.id, user_id=u.id, notifications_enabled=False)
    test_session.add_all([sub1, sub2])
    await test_session.commit()

    # Query subscriptions
    result = await list_user_subscriptions(test_session, u.id)
    assert len(result) == 2
    org_ids = [item.organization.id for item in result]
    assert org1.id in org_ids
    assert org2.id in org_ids
    for item in result:
        assert isinstance(item.organization.followers_count, int)
        assert item.organization.followers_count >= 1


@pytest.mark.asyncio
async def test_auth_service_race_condition_resilience(test_session):
    """
    1. get_or_create_user wraps user creation in try..except IntegrityError
    with session.rollback() and selects existing user.
    """
    from app.services.auth_service import get_or_create_user
    from app.schemas.telegram import TelegramUserPayload

    tg_user = TelegramUserPayload(id=987654321, username="race_test_user", first_name="Race", last_name="User")
    
    # 1. First call creates user
    u1 = await get_or_create_user(test_session, tg_user)
    assert u1.telegram_id == 987654321

    # 2. Second call handles idempotently without error
    u2 = await get_or_create_user(test_session, tg_user)
    assert u2.id == u1.id


@pytest.mark.asyncio
async def test_rejected_event_resubmission_resets_to_pending(test_session):
    """
    2. update_organizer_event: When an event was REJECTED, updating it
    resets its status to PENDING and clears rejection_reason.
    """
    from app.services.event_service import update_organizer_event
    from app.schemas.event import EventUpdate

    org_user = User(id=922001, telegram_id=922001, username="rejected_editor")
    test_session.add(org_user)
    await test_session.commit()

    ev = Event(
        title="Rejected Event",
        description="Initial bad description",
        category_id="parties",
        city_id="makhachkala",
        address="Ленина 10",
        venue_name="Venue 1",
        start_at=datetime.now(timezone.utc) + timedelta(days=5),
        organizer_user_id=org_user.id,
        status=EventStatus.REJECTED.value,
        rejection_reason="Violates community guidelines",
    )
    test_session.add(ev)
    await test_session.commit()

    # Update event content
    update_data = EventUpdate(
        description="Fixed friendly description compliant with guidelines",
    )
    updated_ev, _ = await update_organizer_event(test_session, ev.id, update_data, org_user.id)
    assert updated_ev.status == EventStatus.PENDING.value
    assert updated_ev.rejection_reason is None


@pytest.mark.asyncio
async def test_rsvp_and_interest_forbidden_for_unpublished_events(test_session):
    """
    3. add_event_rsvp and add_event_interest reject actions on non-published events.
    """
    from app.services.event_service import add_event_rsvp, add_event_interest, EventValidationError

    u = User(id=923001, telegram_id=923001, username="pending_rsvp_user")
    test_session.add(u)
    
    pending_ev = Event(
        title="Pending Event",
        description="Not published yet",
        category_id="parties",
        city_id="makhachkala",
        address="Ленина 10",
        venue_name="Club",
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        organizer_user_id=u.id,
        status=EventStatus.PENDING.value,
    )
    test_session.add(pending_ev)
    await test_session.commit()

    with pytest.raises(EventValidationError, match="опубликованных мероприятий"):
        await add_event_rsvp(test_session, pending_ev.id, u.id)

    with pytest.raises(EventValidationError, match="опубликованных мероприятий"):
        await add_event_interest(test_session, pending_ev.id, u.id)


@pytest.mark.asyncio
async def test_rejection_reason_privacy_and_inline_published_filter(test_session):
    """
    4. get_event_details hides rejection_reason for non-owner non-admin.
    Inline query does not return non-published events.
    """
    from app.services.event_service import get_event_details, EventNotFoundError
    from app.services.telegram_bot import handle_inline_query

    owner = User(id=924001, telegram_id=924001, username="priv_owner")
    other_user = User(id=924002, telegram_id=924002, username="priv_viewer")
    test_session.add_all([owner, other_user])
    await test_session.commit()

    rejected_ev = Event(
        title="Secret Rejected",
        description="Secret description",
        category_id="parties",
        city_id="makhachkala",
        address="Ленина 10",
        venue_name="Underground",
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        organizer_user_id=owner.id,
        status=EventStatus.REJECTED.value,
        rejection_reason="Internal moderation note",
    )
    test_session.add(rejected_ev)
    await test_session.commit()

    # Owner sees rejection_reason
    owner_details = await get_event_details(test_session, rejected_ev.id, owner.id)
    assert owner_details.rejection_reason == "Internal moderation note"

    # Other user CANNOT access rejected event (raises 404 EventNotFoundError)
    with pytest.raises(EventNotFoundError):
        await get_event_details(test_session, rejected_ev.id, other_user.id)

    # Inline query for event_<id> returns empty state card (no event returned) for non-published event
    inline_res = await handle_inline_query(test_session, {"id": "test_q", "query": f"event_{rejected_ev.id}", "offset": ""})
    results = inline_res.get("results", [])
    assert len(results) == 1
    assert results[0]["id"] == "empty_state"


@pytest.mark.asyncio
async def test_audience_and_insights_exclude_deleted_events(test_session):
    """
    5. audience_service & insights_service exclude DELETED events.
    list_user_organizations and admin_list_organizations return plan='free' when expired.
    """
    from app.services.audience_service import get_organizer_audience
    from app.services.insights_service import get_organizer_insights
    from app.services.organization_service import list_user_organizations
    from app.api.v1.admin import admin_list_organizations

    u = User(id=925001, telegram_id=925001, username="insights_org_owner")
    test_session.add(u)
    await test_session.commit()

    org = Organization(
        name="Expired Pro Org",
        slug="expired-pro-org",
        category="parties",
        city_id="makhachkala",
        owner_user_id=u.id,
        status=OrganizationStatus.ACTIVE.value,
    )
    test_session.add(org)
    await test_session.commit()

    # Expired Pro Plan (expired yesterday)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    plan = OrganizationPlan(
        organization_id=org.id,
        plan=PlanType.PRO.value,
        status=PlanStatus.ACTIVE.value,
        starts_at=yesterday - timedelta(days=30),
        expires_at=yesterday,
    )
    test_session.add(plan)

    # Deleted Event
    deleted_ev = Event(
        title="Deleted Event",
        description="Should not appear in audience/insights",
        category_id="parties",
        city_id="makhachkala",
        address="Ленина 10",
        venue_name="Closed Hall",
        start_at=datetime.now(timezone.utc) + timedelta(days=1),
        organizer_user_id=u.id,
        organization_id=org.id,
        status=EventStatus.DELETED.value,
    )
    test_session.add(deleted_ev)
    await test_session.commit()

    # 1. Audience metrics should have 0 events
    aud = await get_organizer_audience(test_session, u.id, org.id)
    assert aud.organizations[0].events_count == 0

    # 2. Insights should have 0 events
    ins = await get_organizer_insights(test_session, u.id)
    assert ins.events.total_events == 0

    # 3. list_user_organizations should return plan='free' because expired
    org_list = await list_user_organizations(test_session, u.id)
    target_summary = next(o for o in org_list if o.id == org.id)
    assert target_summary.plan == "free"

    # 4. admin_list_organizations should also return plan='free' because expired
    admin_tg_id = settings.admin_ids[0] if settings.admin_ids else 123456789
    admin_u = User(id=925099, telegram_id=admin_tg_id, username="admin_checker")
    admin_orgs = await admin_list_organizations(admin=admin_u, session=test_session)
    admin_summary = next(o for o in admin_orgs if o.id == org.id)
    assert admin_summary.plan == "free"


@pytest.mark.asyncio
async def test_payment_activation_notification_uses_pro_expiration_date(test_session, monkeypatch):
    """
    CRITICAL: verify_and_activate_order sends notification with +30 days expiration date
    from OrganizationPlan, NOT the 1-hour checkout TTL order.expires_at.
    """
    from app.services.payment_service import PaymentService, set_payment_provider_override, ensure_utc
    from app.services.payment.mock_provider import MockYooKassaProvider
    from app.models.payment import PaymentOrder, PaymentOrderStatus

    provider = MockYooKassaProvider()
    set_payment_provider_override(provider)
    monkeypatch.setattr(settings, "PAYMENTS_ENABLED", True)

    u = User(id=926001, telegram_id=926001, username="notif_date_buyer")
    org = Organization(
        name="Pro Buyer Org",
        slug="pro-buyer-org",
        category="concerts",
        city_id="makhachkala",
        owner_user_id=u.id,
        status=OrganizationStatus.ACTIVE.value,
    )
    test_session.add_all([u, org])
    await test_session.commit()

    # 1. Create order: order.expires_at is 1 hour
    order, _ = await PaymentService.create_pro_order(
        session=test_session,
        organization_id=org.id,
        user=u,
        provider=provider
    )
    assert ensure_utc(order.expires_at) < datetime.now(timezone.utc) + timedelta(hours=2)

    # 2. Intercept send_telegram_notification to verify exp_fmt
    sent_notifications = []

    async def mock_send(chat_id, text, parse_mode=None, reply_markup=None):
        sent_notifications.append({"chat_id": chat_id, "text": text})
        return True

    monkeypatch.setattr("app.services.payment_service.send_telegram_notification", mock_send)

    # 3. Simulate payment completion and activate order
    provider.simulate_payment_status(order.provider_payment_id, "succeeded", paid=True)
    activated_order = await PaymentService.verify_and_activate_order(test_session, order, provider=provider)

    assert activated_order.status == PaymentOrderStatus.SUCCEEDED.value
    assert len(sent_notifications) == 1

    msg = sent_notifications[0]["text"]
    # Check that date in notification is ~30 days in the future, NOT today + 1 hour!
    exp_30d = (datetime.now(timezone.utc) + timedelta(days=settings.PRO_SUBSCRIPTION_DAYS)).strftime("%d.%m.%Y")
    assert exp_30d in msg, f"Expected {exp_30d} in message '{msg}'"


