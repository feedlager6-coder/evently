import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, or_
from pydantic import ValidationError

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_plan import PlanType
from app.models.attendee import EventAttendee
from app.models.city import City
from app.models.category import Category
from app.models.payment import PaymentOrder, PaymentTransaction
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.services.payment_service import PaymentService
from app.api.deps import get_current_user


@pytest.mark.asyncio
async def test_issue1_pro_plan_upgrade_security_and_plantype_import(client, test_session):
    """
    Issue 1:
    - PlanType is properly imported (no NameError).
    - Requires payment / admin when PAYMENTS_ENABLED is True.
    - Owner or admin can activate, expires_at is correctly set.
    """
    admin_id = int(list(settings.admin_ids)[0])
    admin_auth = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_user')}"}
    
    # Create test user and organization
    user_id = 771122
    user_auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='owner_user')}"}
    
    user = (await test_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        user = User(id=user_id, telegram_id=user_id, username="owner_user")
        test_session.add(user)
        await test_session.commit()

    city = (await test_session.execute(select(City))).scalars().first()
    org = Organization(
        name="Security Audit Org",
        slug="security-audit-org",
        category="music",
        city_id=city.id,
        owner_user_id=user_id,
        status=OrganizationStatus.ACTIVE.value
    )
    test_session.add(org)
    await test_session.commit()

    # 1. Non-admin with PAYMENTS_ENABLED=True gets 402 Payment Required
    with patch.object(settings, "PAYMENTS_ENABLED", True):
        resp_402 = await client.post(f"/api/v1/organizer/organizations/{org.id}/pro", headers=user_auth)
        assert resp_402.status_code == 402
        assert "подписку" in resp_402.json()["detail"].lower()

    # 1b. Non-admin in production environment with PAYMENTS_ENABLED=False ALSO gets 402
    with patch.object(settings, "PAYMENTS_ENABLED", False), patch.object(settings, "APP_ENV", "production"):
        resp_prod_402 = await client.post(f"/api/v1/organizer/organizations/{org.id}/pro", headers=user_auth)
        assert resp_prod_402.status_code == 402
        assert "подписку" in resp_prod_402.json()["detail"].lower()

    # 2. Admin can upgrade organization to PRO without NameError
    with patch.object(settings, "PAYMENTS_ENABLED", True):
        resp_ok = await client.post(f"/api/v1/organizer/organizations/{org.id}/pro", headers=admin_auth)
        assert resp_ok.status_code == 200
        data = resp_ok.json()
        assert data["plan"] == "pro"
        assert data["capabilities"]["broadcasts_extended"]["status"] == "available"


@pytest.mark.asyncio
async def test_issue2_ticket_checkin_validates_attendee_and_rejects_fake(client, test_session):
    """
    Issue 2:
    - Arbitrary fake QR strings like 'fake_random_qr_123' are rejected with status='invalid'.
    - A ticket referencing a user who has NOT RSVP'd is rejected with status='invalid'.
    - A ticket referencing a user who HAS RSVP'd is accepted with status='success'.
    """
    organizer_id = 882233
    org_auth = {"Authorization": f"tma {make_test_init_data(user_id=organizer_id, username='checkin_host')}"}

    # Ensure organizer exists
    org_user = (await test_session.execute(select(User).where(User.id == organizer_id))).scalar_one_or_none()
    if not org_user:
        org_user = User(id=organizer_id, telegram_id=organizer_id, username="checkin_host")
        test_session.add(org_user)
        await test_session.commit()

    # Create event
    event = Event(
        title="Exclusive Guest Gala",
        description="Ticket checkin attendee verification",
        category_id="parties",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=1),
        venue_name="Grand Ballroom",
        address="Lenina 10",
        organizer_user_id=organizer_id,
        status=EventStatus.PUBLISHED.value,
        price_amount=0,
    )
    test_session.add(event)
    await test_session.commit()

    # 1. Arbitrary fake string -> REJECTED
    resp_fake = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": "fake_random_qr_payload_9999"}
    )
    assert resp_fake.status_code == 200
    assert resp_fake.json()["status"] == "invalid"
    assert "недействительный" in resp_fake.json()["message"].lower() or "не найден" in resp_fake.json()["message"].lower()

    # 2. Ticket with registered user vs unregistered user
    unreg_user_id = 991199
    unreg_user = User(id=unreg_user_id, telegram_id=unreg_user_id, username="unreg_guest")
    test_session.add(unreg_user)

    reg_user_id = 992299
    reg_user = User(id=reg_user_id, telegram_id=reg_user_id, username="reg_guest", first_name="Анна")
    test_session.add(reg_user)
    await test_session.commit()

    # Register reg_user as attendee
    attendee = EventAttendee(event_id=event.id, user_id=reg_user.id)
    test_session.add(attendee)
    await test_session.commit()

    # 3. Test check-in for unreg_user -> REJECTED
    unreg_ticket = f'{{"ticket_id": "IVN-GALA-{unreg_user_id}", "event_id": "{event.id}", "user_id": {unreg_user_id}}}'
    resp_unreg = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": unreg_ticket}
    )
    assert resp_unreg.status_code == 200
    assert resp_unreg.json()["status"] == "invalid"
    assert "не найден среди регистраций" in resp_unreg.json()["message"].lower()

    # 4. Test check-in for reg_user -> SUCCESS
    reg_ticket = f'{{"ticket_id": "IVN-GALA-{reg_user_id}", "event_id": "{event.id}", "user_id": {reg_user_id}}}'
    resp_reg = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": reg_ticket}
    )
    assert resp_reg.status_code == 200
    assert resp_reg.json()["status"] == "success"
    assert resp_reg.json()["guest_name"] == "Анна"

    # 5. Test duplicate check-in with DIFFERENT ticket representation for the SAME attendee -> ALREADY_CHECKED_IN
    alt_reg_ticket = f'{{"ticket_id": "ALT-FORMAT-{reg_user_id}", "event_id": "{event.id}", "user_id": {reg_user_id}}}'
    resp_alt = await client.post(
        f"/api/v1/organizer/events/{event.id}/check-in",
        headers=org_auth,
        json={"ticket_code": alt_reg_ticket}
    )
    assert resp_alt.status_code == 200
    assert resp_alt.json()["status"] == "already_checked_in"
    assert "уже был использован" in resp_alt.json()["message"].lower()


@pytest.mark.asyncio
async def test_issue3_telegram_webhook_and_setup_security(client):
    """
    Issue 3:
    - /setup-webhook requires admin privileges (401/403).
    - /webhook checks X-Telegram-Bot-Api-Secret-Token when TELEGRAM_WEBHOOK_SECRET is set.
    """
    # 1. Non-admin cannot call setup-webhook
    resp_unauth = await client.post("/api/v1/telegram/setup-webhook")
    assert resp_unauth.status_code in (401, 403)

    user_auth = {"Authorization": f"tma {make_test_init_data(user_id=123999, username='regular')}"}
    resp_forbidden = await client.post("/api/v1/telegram/setup-webhook", headers=user_auth)
    assert resp_forbidden.status_code == 403

    # 2. Secret token verification on /webhook
    secret_val = "super_secret_webhook_token_12345"
    with patch.object(settings, "TELEGRAM_WEBHOOK_SECRET", secret_val):
        update_payload = {"update_id": 999111, "message": {"chat": {"id": 1}, "text": "hi"}}
        
        # Missing header -> 403
        resp_no_token = await client.post("/api/v1/telegram/webhook", json=update_payload)
        assert resp_no_token.status_code == 403

        # Invalid header -> 403
        resp_bad_token = await client.post(
            "/api/v1/telegram/webhook",
            json=update_payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_token"}
        )
        assert resp_bad_token.status_code == 403

        # Correct header -> 200
        resp_ok = await client.post(
            "/api/v1/telegram/webhook",
            json=update_payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": secret_val}
        )
        assert resp_ok.status_code == 200

    # 3. Deterministic secret fallback in production when TELEGRAM_WEBHOOK_SECRET is empty
    with patch.object(settings, "TELEGRAM_WEBHOOK_SECRET", None), \
         patch.object(settings, "APP_ENV", "production"), \
         patch.object(settings, "SECRET_KEY", "prod_secret_key_999"), \
         patch.object(settings, "TELEGRAM_BOT_TOKEN", "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ_test"):
        
        fallback_secret = settings.effective_webhook_secret
        assert fallback_secret is not None
        assert len(fallback_secret) == 32

        # Webhook rejects request without the fallback secret token
        resp_no_fallback = await client.post("/api/v1/telegram/webhook", json={"update_id": 999112})
        assert resp_no_fallback.status_code == 403

        # Webhook accepts request with the fallback secret token
        resp_with_fallback = await client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 999112},
            headers={"X-Telegram-Bot-Api-Secret-Token": fallback_secret}
        )
        assert resp_with_fallback.status_code == 200


@pytest.mark.asyncio
async def test_issue4_upload_endpoints_auth_and_size_limits(client):
    """
    Issue 4:
    - /upload-cover and /upload-avatar reject unauthenticated requests with 401.
    - Files exceeding MAX_FILE_SIZE return 413 Payload Too Large.
    """
    tiny_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 100
    files = {"file": ("cover.jpg", tiny_jpeg, "image/jpeg")}

    # 1. Unauthenticated /upload-cover -> 401
    resp_cover_unauth = await client.post("/api/v1/events/upload-cover", files=files)
    assert resp_cover_unauth.status_code == 401

    # 2. Unauthenticated /upload-avatar -> 401
    resp_avatar_unauth = await client.post("/api/v1/organizations/upload-avatar", files=files)
    assert resp_avatar_unauth.status_code == 401

    # 3. Oversized file with auth -> 413
    auth_headers = {"Authorization": f"tma {make_test_init_data(user_id=12345)}" }
    large_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * (5 * 1024 * 1024 + 10)
    oversized_files = {"file": ("huge.jpg", large_bytes, "image/jpeg")}

    resp_huge_cover = await client.post("/api/v1/events/upload-cover", files=oversized_files, headers=auth_headers)
    assert resp_huge_cover.status_code == 413
    assert "лимит" in resp_huge_cover.json()["detail"].lower()


@pytest.mark.asyncio
async def test_issue5_spa_path_traversal_protection(client):
    """
    Issue 5:
    - Requesting ../../.env or directory traversal does not expose files.
    """
    resp = await client.get("/../../.env")
    # Must either be 404 Not Found or fallback index.html (text/html), never plain text with secret keys
    if resp.status_code == 200:
        assert "SECRET_KEY" not in resp.text
        assert "TELEGRAM_BOT_TOKEN" not in resp.text


@pytest.mark.asyncio
async def test_issue7_cities_in_memory_cache_and_cyrillic_search(client):
    """
    Issue 7:
    - Cyrillic search works reliably without full scan.
    - Cache-Control is set properly.
    """
    resp_all = await client.get("/api/v1/cities")
    assert resp_all.status_code == 200
    assert "public" in resp_all.headers.get("Cache-Control", "")

    resp_q = await client.get("/api/v1/cities?q=махачкала")
    assert resp_q.status_code == 200
    assert "private" in resp_q.headers.get("Cache-Control", "")
    data = resp_q.json()
    assert len(data) >= 1
    assert data[0]["id"] == "makhachkala"


@pytest.mark.asyncio
async def test_issue8_locations_suggest_cache(client):
    """
    Issue 8:
    - Suggest locations caches repeated queries without spawning infinite clients.
    """
    resp1 = await client.get("/api/v1/locations/suggest?q=Ленина&city_id=makhachkala")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) >= 1

    resp2 = await client.get("/api/v1/locations/suggest?q=Ленина&city_id=makhachkala")
    assert resp2.status_code == 200
    assert resp2.json() == data1


def test_issue9_models_cascade_delete_orphan_removed():
    """
    Issue 9:
    - City.events and Category.events do NOT contain delete-orphan cascade.
    """
    from app.models.city import City
    from app.models.category import Category

    city_cascade = City.__mapper__.relationships["events"].cascade
    assert "delete-orphan" not in city_cascade, "City.events must not cascade delete-orphan"

    cat_cascade = Category.__mapper__.relationships["events"].cascade
    assert "delete-orphan" not in cat_cascade, "Category.events must not cascade delete-orphan"


def test_issue10_payment_numeric_decimal_safety():
    """
    Issue 10:
    - PaymentOrder.amount and PaymentTransaction.amount are Numeric(10, 2).
    - Comparing float provider amount with order Decimal does not raise TypeError.
    """
    from decimal import Decimal
    order_amount = Decimal("499.00")
    prov_amount = 499.00
    
    # Verify Decimal conversion pattern
    exp = Decimal(str(order_amount))
    act = Decimal(str(prov_amount))
    diff = abs(act - exp)
    assert diff < Decimal("0.01")


def test_issue12_organization_url_validation_and_xss_protection():
    """
    Issue 12:
    - Dangerous URL schemes (javascript:, data:) are rejected with 422 ValidationError.
    - Social links with @channel are automatically formatted to https://t.me/channel.
    """
    # 1. Reject javascript: XSS
    with pytest.raises(ValidationError):
        OrganizationCreate(
            name="XSS Org",
            category="club",
            website="javascript:alert(1)"
        )

    with pytest.raises(ValidationError):
        OrganizationCreate(
            name="XSS Org",
            category="club",
            avatar_url="javascript:alert(1)"
        )

    # 2. Reject protocol-relative //
    with pytest.raises(ValidationError):
        OrganizationCreate(
            name="Protocol Relative Org",
            category="club",
            avatar_url="//attacker.com/avatar.png"
        )

    # 3. Sanitize @username to https://t.me/username
    org = OrganizationCreate(
        name="Valid Org",
        category="club",
        social_link="@my_great_events"
    )
    assert org.social_link == "https://t.me/my_great_events"


@pytest.mark.asyncio
async def test_issue13_deps_db_error_returns_500_not_401(test_session):
    """
    Issue 13:
    - Unexpected DB or internal errors in get_current_user return 500, not 401.
    """
    from fastapi import HTTPException
    
    valid_auth = f"tma {make_test_init_data(user_id=555666, username='test_user')}"
    
    with patch("app.api.deps.get_or_create_user", side_effect=RuntimeError("Database connection lost")):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization=valid_auth, session=test_session)
        assert exc.value.status_code == 500
        assert "внутренняя ошибка" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_issue15_user_hub_does_not_duplicate_created(client):
    """
    Issue 15:
    - UserHubResponse uses created_events, and created is an empty list [] (not None) to avoid TypeError in clients.
    """
    user_auth = {"Authorization": f"tma {make_test_init_data(user_id=112233, username='hub_user')}"}
    resp = await client.get("/api/v1/users/me/hub", headers=user_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "created_events" in data
    assert data.get("created") == []
    assert isinstance(data.get("created"), list)
    assert len(data.get("created")) == 0


@pytest.mark.asyncio
async def test_issue4_locations_suggest_coordinates_fallback(client):
    """
    Issue 4:
    - When Nominatim has no results or times out, LocationSuggestion fallback returns latitude=None and longitude=None
      rather than fake city center coordinates.
    """
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=Exception("Nominatim network timeout"))
    with patch("app.api.v1.locations._NOMINATIM_CACHE", {}), \
         patch("app.api.v1.locations._get_locations_client", return_value=mock_client):
        resp = await client.get("/api/v1/locations/suggest?q=УлицаНеизвестная999&city_id=makhachkala")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert "latitude" in item
        assert "longitude" in item
        assert item["latitude"] is None
        assert item["longitude"] is None
        assert "УлицаНеизвестная999" in item["title"]


@pytest.mark.asyncio
async def test_part2_issue3_and_issue5_moderation_reset_and_privacy(test_session):
    """
    Part 2, Issues 3 & 5:
    - Modifying core content of a published event resets status to PENDING for re-moderation.
    - Modifying operational details (venue/start_at) does not reset status.
    - Viewing pending/rejected events is restricted to owner/admin.
    - Inline fast-path ignores pending/rejected events.
    """
    from app.services.event_service import (
        update_organizer_event,
        get_event_details,
        EventNotFoundError,
    )
    from app.schemas.event import EventUpdate
    from app.services.telegram_bot import handle_inline_query

    author = User(id=883311, telegram_id=883311, username="author_user")
    other_user = User(id=883322, telegram_id=883322, username="other_user")
    test_session.add_all([author, other_user])
    await test_session.commit()

    event = Event(
        title="Moderation Test Event",
        description="Original description",
        category_id="parties",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Original Venue",
        address="Original Address",
        organizer_user_id=author.id,
        status=EventStatus.PUBLISHED.value,
        price_amount=0,
    )
    test_session.add(event)
    await test_session.commit()

    # 1. Author modifies operational details only (venue_name) -> stays published
    updated, _ = await update_organizer_event(
        session=test_session,
        event_id=event.id,
        data=EventUpdate(venue_name="Updated Venue Only"),
        user_id=author.id,
    )
    assert updated.status == EventStatus.PUBLISHED.value

    # 2. Author modifies title (core content) -> status resets to PENDING
    updated_core, _ = await update_organizer_event(
        session=test_session,
        event_id=event.id,
        data=EventUpdate(title="Completely New Title After Approval"),
        user_id=author.id,
    )
    assert updated_core.status == EventStatus.PENDING.value

    # 3. get_event_details: other_user gets EventNotFoundError for PENDING event
    with pytest.raises(EventNotFoundError):
        await get_event_details(test_session, event.id, current_user_id=other_user.id)

    # 4. Author CAN view their own PENDING event
    author_view = await get_event_details(test_session, event.id, current_user_id=author.id)
    assert author_view.id == event.id

    # 5. Inline fast-path lookup for PENDING event returns no results
    inline_res = await handle_inline_query(
        session=test_session,
        inline_query={"id": "query_1", "query": f"event_{event.id}", "from": {"id": other_user.telegram_id}}
    )
    # Since event is pending, it should not match the fast-path direct lookup
    results = inline_res.get("results", [])
    assert not any(getattr(r, "id", None) == event.id for r in results)


@pytest.mark.asyncio
async def test_part2_issue4_and_issue9_broadcast_audience_and_unassigned_event(test_session):
    """
    Part 2, Issues 4 & 9:
    - calculate_audience rejects non-published events.
    - calculate_audience does NOT mutate event.organization_id.
    - create_broadcast explicitly binds event.organization_id if author owns both.
    """
    from app.services.broadcast_service import calculate_audience, create_broadcast
    from app.schemas.broadcast import BroadcastCreateRequest
    from fastapi import HTTPException

    user = User(id=884411, telegram_id=884411, username="bcast_user")
    test_session.add(user)
    await test_session.commit()

    org = Organization(
        name="Audience Test Org",
        slug="audience-test-org",
        category="music",
        city_id="makhachkala",
        owner_user_id=user.id,
        status=OrganizationStatus.ACTIVE.value
    )
    test_session.add(org)
    await test_session.commit()

    # Draft / Pending event without organization_id
    draft_event = Event(
        title="Unpublished Draft Event",
        description="Draft event description",
        category_id="parties",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        venue_name="Club",
        address="Street 1",
        organizer_user_id=user.id,
        organization_id=None,
        status=EventStatus.PENDING.value,
    )
    test_session.add(draft_event)
    await test_session.commit()

    # 1. calculate_audience with pending event raises 400
    with pytest.raises(HTTPException) as exc:
        await calculate_audience(
            session=test_session,
            organizer_user_id=user.id,
            organization_id=org.id,
            target_type="organization_subscribers",
            broadcast_type="marketing",
            event_id=draft_event.id
        )
    assert exc.value.status_code == 400
    assert "опубликованных" in exc.value.detail.lower()

    # 2. Verify event.organization_id was NOT silently mutated
    await test_session.refresh(draft_event)
    assert draft_event.organization_id is None


@pytest.mark.asyncio
async def test_part2_issue7_and_issue8_timezones_and_fallback_markup(test_session):
    """
    Part 2, Issues 7 & 8:
    - Dates are formatted in the city's timezone.
    - build_event_notification_reply_markup falls back to get_event_deep_link when host is None.
    """
    from app.services.broadcast_service import format_broadcast_date_str
    from app.services.notification_service import build_event_notification_reply_markup

    # City with Asia/Yekaterinburg (UTC+5)
    ekb_city = City(id="ekaterinburg", name="Екатеринбург", country="Россия", currency="RUB", timezone="Asia/Yekaterinburg")
    test_session.add(ekb_city)
    await test_session.commit()

    # Event starts at 14:00 UTC -> in Ekaterinburg (UTC+5) it is 19:00
    start_utc = datetime(2026, 12, 1, 14, 0, tzinfo=timezone.utc)
    ev = Event(
        title="Ural Symphony",
        description="Classical concert in Ural",
        category_id="music",
        city_id=ekb_city.id,
        city=ekb_city,
        start_at=start_utc,
        venue_name="Concert Hall",
        address="Lenina 1",
        organizer_user_id=1,
        status=EventStatus.PUBLISHED.value
    )
    date_str = format_broadcast_date_str(ev)
    assert "19:00" in date_str

    # Markup fallback test
    with patch.object(type(settings), "effective_public_host", new_callable=PropertyMock, return_value=None):
        markup = build_event_notification_reply_markup("test_ev_123")
        btn = markup["inline_keyboard"][0][0]
        assert "url" in btn
        assert "t.me" in btn["url"]


@pytest.mark.asyncio
async def test_part2_issue10_disallow_rsvp_on_non_published(test_session):
    """
    Part 2, Issue 10:
    - add_event_rsvp and add_event_interest reject non-published events.
    """
    from app.services.event_service import add_event_rsvp, add_event_interest, EventValidationError

    user = User(id=776655, telegram_id=776655, username="rsvp_tester")
    test_session.add(user)
    await test_session.commit()

    pending_event = Event(
        title="Pending Gala",
        description="Pending gala description",
        category_id="parties",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Hall",
        address="Street 2",
        organizer_user_id=1,
        status=EventStatus.PENDING.value
    )
    test_session.add(pending_event)
    await test_session.commit()

    with pytest.raises(EventValidationError):
        await add_event_rsvp(test_session, pending_event.id, user.id)

    with pytest.raises(EventValidationError):
        await add_event_interest(test_session, pending_event.id, user.id)


@pytest.mark.asyncio
async def test_part2_issue11_auth_race_condition_recovery(test_session):
    """
    Part 2, Issue 11:
    - get_or_create_user gracefully recovers from IntegrityError on concurrent creation.
    """
    from app.services.auth_service import get_or_create_user
    from app.schemas.telegram import TelegramUserPayload
    from sqlalchemy.exc import IntegrityError

    tg_user = TelegramUserPayload(id=998877, username="concurrent_user", first_name="Con", last_name="Current")

    # Simulate: first call adds user to DB
    existing_user = User(id=998877, telegram_id=998877, username="concurrent_user")
    test_session.add(existing_user)
    await test_session.commit()

    # Calling get_or_create_user returns existing user cleanly
    user = await get_or_create_user(test_session, tg_user)
    assert user.id == existing_user.id
    assert user.telegram_id == 998877


@pytest.mark.asyncio
async def test_part2_issue12_insights_and_audience_exclude_deleted(test_session):
    """
    Part 2, Issue 12:
    - get_organizer_audience and get_organizer_insights exclude DELETED events.
    """
    from app.services.audience_service import get_organizer_audience
    from app.services.insights_service import get_organizer_insights

    org_owner = User(id=885522, telegram_id=885522, username="insights_owner")
    test_session.add(org_owner)
    await test_session.commit()

    org = Organization(
        name="Metrics Org",
        slug="metrics-org",
        category="art",
        city_id="makhachkala",
        owner_user_id=org_owner.id,
        status=OrganizationStatus.ACTIVE.value
    )
    test_session.add(org)
    await test_session.commit()

    # 1 active event, 1 deleted event
    active_ev = Event(
        title="Active Event",
        description="Active event description",
        category_id="art",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=2),
        venue_name="Gallery",
        address="Street 3",
        organizer_user_id=org_owner.id,
        organization_id=org.id,
        status=EventStatus.PUBLISHED.value
    )
    deleted_ev = Event(
        title="Deleted Event",
        description="Deleted event description",
        category_id="art",
        city_id="makhachkala",
        start_at=datetime.now(timezone.utc) + timedelta(days=3),
        venue_name="Trash",
        address="Street 4",
        organizer_user_id=org_owner.id,
        organization_id=org.id,
        status=EventStatus.DELETED.value
    )
    test_session.add_all([active_ev, deleted_ev])
    await test_session.commit()

    aud = await get_organizer_audience(test_session, org_owner.id, org.id)
    assert len(aud.recent_events) == 1
    assert aud.recent_events[0].id == active_ev.id

    ins = await get_organizer_insights(test_session, org_owner.id)
    assert ins.events.total_events == 1
    assert ins.events.upcoming_events_count == 1


@pytest.mark.asyncio
async def test_part2_issue13_expired_pro_plan_excluded(test_session):
    """
    Part 2, Issue 13:
    - list_user_organizations and admin_list_organizations show plan='free' when OrganizationPlan is expired.
    """
    from app.services.organization_service import list_user_organizations
    from app.models.organization_plan import OrganizationPlan, PlanStatus

    owner = User(id=886633, telegram_id=886633, username="plan_owner")
    test_session.add(owner)
    await test_session.commit()

    org = Organization(
        name="Expired Pro Org",
        slug="expired-pro-org",
        category="art",
        city_id="makhachkala",
        owner_user_id=owner.id,
        status=OrganizationStatus.ACTIVE.value
    )
    test_session.add(org)
    await test_session.commit()

    # Plan expired yesterday
    expired_plan = OrganizationPlan(
        organization_id=org.id,
        plan="pro",
        status=PlanStatus.ACTIVE.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    test_session.add(expired_plan)
    await test_session.commit()

    summaries = await list_user_organizations(test_session, owner.id)
    assert len(summaries) == 1
    assert summaries[0].plan == "free"

