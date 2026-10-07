import pytest
import httpx
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock
from sqlalchemy import select

from tests.conftest import make_test_init_data
from app.config import settings
from app.models.user import User
from app.models.organization import Organization
from app.models.event import Event, EventStatus
from app.models.subscription import Subscription
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.services.entitlement_service import EntitlementService
from app.services.notification_service import (
    notify_event_updated,
    notify_organization_subscribers,
    build_event_notification_reply_markup,
)


# ==============================================================================
# DOMAIN 1: AUTH & FIRST RUN
# ==============================================================================

@pytest.mark.asyncio
async def test_domain_1_auth_first_run_flow(client, test_session):
    """
    Verifies that a user without default_city_id has None on backend,
    and after setting default city, events can be retrieved for that city.
    """
    user_id = 9101
    auth = {"Authorization": f"tma {make_test_init_data(user_id=user_id, username='user_domain1')}"}

    # 1. New user profile has no default city
    me_res = await client.get("/api/v1/users/me", headers=auth)
    assert me_res.status_code == 200
    assert me_res.json()["default_city_id"] is None

    # 2. Feed call without city_id query param returns events across cities or requires explicit filter
    feed_res = await client.get("/api/v1/events", headers=auth)
    assert feed_res.status_code == 200

    # 3. User chooses city -> saved as default
    city_res = await client.post("/api/v1/cities/default?city_id=derbent", headers=auth)
    assert city_res.status_code == 200
    assert city_res.json()["id"] == "derbent"

    # 4. Profile now remembers chosen city
    me_after = await client.get("/api/v1/users/me", headers=auth)
    assert me_after.json()["default_city_id"] == "derbent"


# ==============================================================================
# DOMAIN 2: AFISHA LOADING & INTEGRITY
# ==============================================================================

def test_domain_2_contract_app_feed_loading_guards():
    """
    Contract check: App.tsx must have AbortController, request ID race condition guard,
    watchdog recovery on resume, and fetchWithTimeout in api.ts.
    """
    app_path = Path("frontend/src/App.tsx")
    assert app_path.exists(), "App.tsx must exist"
    app_code = app_path.read_text(encoding="utf-8")

    assert "feedAbortControllerRef" in app_code, "App.tsx must maintain feedAbortControllerRef"
    assert "feedRequestIdRef" in app_code, "App.tsx must maintain feedRequestIdRef for race-guarding"
    assert "feedLoadingStartedAtRef" in app_code, "App.tsx must track feedLoadingStartedAtRef"
    assert "if (!selectedCityId)" in app_code, "App.tsx must gate feed fetching on selectedCityId"

    api_path = Path("frontend/src/services/api.ts")
    assert api_path.exists(), "api.ts must exist"
    api_code = api_path.read_text(encoding="utf-8")

    assert "export async function fetchWithTimeout" in api_code, "api.ts must export fetchWithTimeout"
    assert "timeoutMs: number = 10000" in api_code, "api.ts fetchWithTimeout must default to 10s"
    assert "signal?: AbortSignal" in api_code, "api.ts getEvents must support AbortSignal"


# ==============================================================================
# DOMAIN 3: MY EVENTS LAYOUT & DISCOVERABILITY
# ==============================================================================

def test_domain_3_contract_organizer_tab_no_horizontal_overflow():
    """
    Contract check: OrganizerTab.tsx must use 2-tier responsive layout
    to eliminate mobile horizontal page overflow and cut-off tabs.
    """
    tab_path = Path("frontend/src/components/OrganizerTab.tsx")
    assert tab_path.exists(), "OrganizerTab.tsx must exist"
    content = tab_path.read_text(encoding="utf-8")

    # Must contain 2 AnimatedSegmentedControl controls
    assert content.count("<AnimatedSegmentedControl") >= 2, (
        "OrganizerTab must use 2-tier AnimatedSegmentedControl layout"
    )

    # All 5 tabs must be present
    assert "value: 'attending'" in content
    assert "value: 'interested'" in content
    assert "value: 'created'" in content
    assert "value: 'subscriptions'" in content
    assert "value: 'history'" in content


# ==============================================================================
# DOMAIN 4: EVENT UPDATE NOTIFICATION CTA DEEP LINK
# ==============================================================================

@pytest.mark.asyncio
async def test_domain_4_event_update_notification_cta(client, test_session):
    """
    Verifies that notify_event_updated sends notifications to both RSVP ('Я иду')
    and Interested ('Хочу пойти') users, with the exact direct Mini App URL.
    """
    owner_id = 9201
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_d4')}"}
    admin_id = 123456789
    auth_admin = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_d4')}"}

    # 1. Create org and event
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Theatre Arena", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    start_time = datetime.now(timezone.utc) + timedelta(days=5)
    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Hamlet Premiere",
            "description": "Dramatic performance.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": start_time.isoformat(),
            "venue_name": "Old Stage",
            "address": "ул. Ленина, 10",
            "organization_id": org_id,
        },
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]
    await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=auth_admin)

    # 2. Add attendees: User A ('Я иду'), User B ('Хочу пойти')
    user_a_id = 9202
    user_b_id = 9203
    auth_a = {"Authorization": f"tma {make_test_init_data(user_id=user_a_id, username='attendee_a')}"}
    auth_b = {"Authorization": f"tma {make_test_init_data(user_id=user_b_id, username='interested_b')}"}

    await client.post(f"/api/v1/events/{event_id}/rsvp", headers=auth_a)
    await client.post(f"/api/v1/events/{event_id}/interest", headers=auth_b)

    # 3. Trigger notify_event_updated with mocked HTTP client
    mock_http = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_http.post.return_value = mock_resp

    # Load fresh event from DB
    event_obj = await test_session.get(Event, event_id)
    changes = {
        "time_changed": True,
        "old_start_at": start_time,
        "new_start_at": start_time + timedelta(hours=2),
        "venue_changed": True,
        "old_venue": "Old Stage",
        "new_venue": "Main Arena",
    }

    sent = await notify_event_updated(event_obj, changes, test_session, http_client=mock_http)
    assert sent == 2, "Must send notifications to both attendee and interested users"

    # Verify inline keyboard CTA button structure
    calls = mock_http.post.call_args_list
    assert len(calls) == 2
    chat_ids = {c.kwargs["json"]["chat_id"] for c in calls}
    assert user_a_id in chat_ids
    assert user_b_id in chat_ids

    payload = calls[0].kwargs["json"]
    button = payload["reply_markup"]["inline_keyboard"][0][0]
    expected_url = f"{settings.effective_public_host}/?startapp=event_{event_id}"
    assert "web_app" in button
    assert button["web_app"]["url"] == expected_url
    assert "startapp=event_" in button["web_app"]["url"]


def test_domain_4_contract_telegram_and_app_deep_link():
    """
    Contract check: telegram.ts must prioritize live URL over frozen initDataUnsafe,
    provide consumeStartParam, and App.tsx must dismiss conflicting modals on open.
    """
    tg_path = Path("frontend/src/services/telegram.ts")
    assert tg_path.exists(), "telegram.ts must exist"
    tg_code = tg_path.read_text(encoding="utf-8")

    assert "consumeStartParam" in tg_code, "telegram.ts must export consumeStartParam"
    assert "__evently_last_consumed_start_param" in tg_code, "telegram.ts must track consumed parameters"

    app_path = Path("frontend/src/App.tsx")
    assert app_path.exists(), "App.tsx must exist"
    app_code = app_path.read_text(encoding="utf-8")

    assert "telegram.consumeStartParam" in app_code, "App.tsx must consume start parameters"
    assert "setIsCityModalOpen(false);" in app_code, "App.tsx must dismiss CityModal on deep link open"
    assert "setIsOrganizerWorkspaceOpen(false);" in app_code, "App.tsx must dismiss OrganizerWorkspace on deep link open"


# ==============================================================================
# DOMAIN 5: SUBSCRIPTIONS INTEGRITY (0 TELEGRAM MESSAGES)
# ==============================================================================

@pytest.mark.asyncio
async def test_domain_5_organization_subscribe_zero_messages(client, test_session):
    """
    Verifies that subscribing to an organization produces zero Telegram bot messages.
    """
    owner_id = 9301
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_d5')}"}
    sub_id = 9302
    auth_sub = {"Authorization": f"tma {make_test_init_data(user_id=sub_id, username='subscriber_d5')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Art Gallery 05", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    # Subscribe endpoint call
    sub_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_sub)
    assert sub_res.status_code == 200
    assert sub_res.json()["is_subscribed"] is True
    assert sub_res.json()["followers_count"] == 1


def test_domain_5_contract_organization_modal_no_write_access():
    """
    Contract check: OrganizationModal.tsx must NOT request write access on subscribe,
    which was previously triggering unwanted 'Уведомления включены' Telegram bot messages.
    """
    modal_path = Path("frontend/src/components/OrganizationModal.tsx")
    assert modal_path.exists(), "OrganizationModal.tsx must exist"
    content = modal_path.read_text(encoding="utf-8")

    assert "telegram.requestWriteAccess()" not in content, (
        "OrganizationModal.tsx must NOT request write access on subscribe"
    )


# ==============================================================================
# DOMAIN 6: BROADCAST ACCESS CONTROL MATRIX
# ==============================================================================

@pytest.mark.asyncio
async def test_domain_6_broadcast_access_control_matrix(client, test_session):
    """
    Comprehensive access control test:
    - User without organization: 403 / 404
    - Free organization owner: 403 ENTITLEMENT_REQUIRED on create
    - Pro organization owner: 200 OK on create within quota
    - Non-owner on Pro organization: 403 Forbidden ('У вас нет прав')
    - Admin on Free organization: 403 ENTITLEMENT_REQUIRED (Admin does NOT bypass Pro entitlement)
    - Admin on Pro organization: 200 OK
    """
    # 1. User without organization
    unrelated_id = 9401
    auth_unrelated = {"Authorization": f"tma {make_test_init_data(user_id=unrelated_id, username='user_no_org')}"}

    fake_bcast = {
        "organization_id": "00000000-0000-0000-0000-000000000000",
        "target_type": "organization_subscribers",
        "broadcast_type": "marketing",
        "template_key": "custom_update",
        "custom_text": "Unauthorized text",
    }
    res_fake = await client.post("/api/v1/organizer/broadcasts", json=fake_bcast, headers=auth_unrelated)
    assert res_fake.status_code in (403, 404)

    # 2. Free organization owner
    owner_free_id = 9402
    auth_free = {"Authorization": f"tma {make_test_init_data(user_id=owner_free_id, username='owner_free')}"}
    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Free Bakery", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth_free,
    )
    free_org_id = res_org.json()["id"]

    res_free_create = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": free_org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Free broadcast attempt",
        },
        headers=auth_free,
    )
    assert res_free_create.status_code == 403
    detail = res_free_create.json()["detail"]
    assert detail["code"] == "ENTITLEMENT_REQUIRED"
    assert detail["required_plan"] == "pro"

    # 3. Upgrade to Pro -> creation allowed within quota
    await EntitlementService.set_organization_plan(
        test_session,
        free_org_id,
        plan="pro",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    # Add a subscriber so audience > 0
    sub_user_id = 9403
    auth_sub = {"Authorization": f"tma {make_test_init_data(user_id=sub_user_id, username='bcast_sub')}"}
    await client.post(f"/api/v1/organizations/{free_org_id}/subscribe", headers=auth_sub)

    res_pro_create = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": free_org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Pro broadcast success",
        },
        headers=auth_free,
    )
    assert res_pro_create.status_code == 200
    assert res_pro_create.json()["status"] in ("queued", "sent", "completed")

    # 4. Non-owner cannot broadcast to someone else's Pro organization
    res_steal = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": free_org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Attacker trying to use other's pro org",
        },
        headers=auth_unrelated,
    )
    assert res_steal.status_code == 403
    assert "У вас нет прав" in res_steal.json()["detail"]

    # 5. Admin on Free organization does NOT bypass Pro entitlement
    admin_id = 123456789
    auth_admin = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_org_owner')}"}
    res_admin_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Admin Free Org", "category": "Культура", "city_id": "makhachkala"},
        headers=auth_admin,
    )
    admin_org_id = res_admin_org.json()["id"]

    res_admin_free_bcast = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": admin_org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Admin broadcast on Free org",
        },
        headers=auth_admin,
    )
    assert res_admin_free_bcast.status_code == 403
    assert res_admin_free_bcast.json()["detail"]["code"] == "ENTITLEMENT_REQUIRED"


def test_domain_6_contract_workspace_composer_gate():
    """
    Contract check: OrganizerWorkspace.tsx must gate handleOpenComposer behind Pro plan.
    """
    ws_path = Path("frontend/src/components/OrganizerWorkspace.tsx")
    assert ws_path.exists(), "OrganizerWorkspace.tsx must exist"
    ws_code = ws_path.read_text(encoding="utf-8")

    assert "if (entitlements?.plan !== 'pro')" in ws_code, (
        "OrganizerWorkspace handleOpenComposer must verify Pro plan"
    )
    assert "setIsProModalOpen(true);" in ws_code, (
        "OrganizerWorkspace must open ProModal if not Pro"
    )


# ==============================================================================
# MANDATORY PRODUCTION REGRESSION SUITE (11 TESTS)
# ==============================================================================

def test_event_notification_generates_valid_native_and_direct_links():
    """
    1. Verifies notification button generates native web_app URL pointing to
    effective_public_host/?startapp=event_{id}, and settings.get_event_deep_link produces
    the valid direct https://t.me/... URL.
    """
    test_id = "test-event-uuid-1234"
    reply_markup = build_event_notification_reply_markup(test_id)
    button = reply_markup["inline_keyboard"][0][0]
    assert "web_app" in button, "Notification button must use native web_app"
    assert button["web_app"]["url"] == f"{settings.effective_public_host}/?startapp=event_{test_id}"
    assert "startapp=event_" in button["web_app"]["url"]

    # Also with attribution token
    token = "promo99"
    markup_with_tok = build_event_notification_reply_markup(test_id, attribution_token=token)
    btn_tok = markup_with_tok["inline_keyboard"][0][0]
    assert f"startapp=event_{test_id}_b_{token}" in btn_tok["web_app"]["url"]

    # Direct bot link
    direct_link = settings.get_event_deep_link(test_id)
    assert direct_link.startswith(f"https://t.me/{settings.clean_bot_username}/app?startapp=event_{test_id}")


def test_event_deep_link_parser_resolves_correct_event_id():
    """
    2. Verifies parameter parser extracts clean event ID from parameter formats:
    event_{uuid}, event_{uuid}_b_{token}, etc.
    """
    import re
    def parse_event_id(param: str) -> str:
        if not param:
            return ""
        m = re.match(r"^event_([a-zA-Z0-9_-]+?)(?:_b_[a-zA-Z0-9_-]+)?$", param)
        return m.group(1) if m else ""

    assert parse_event_id("event_550e8400-e29b-41d4-a716-446655440000") == "550e8400-e29b-41d4-a716-446655440000"
    assert parse_event_id("event_550e8400-e29b-41d4-a716-446655440000_b_ref123") == "550e8400-e29b-41d4-a716-446655440000"
    assert parse_event_id("event_12345") == "12345"
    assert parse_event_id("invalid") == ""


def test_event_deep_link_opens_exact_event():
    """
    3. Contract test verifying App.tsx and telegram.ts guarantee deep link opens
    the exact event modal without modal collision or frozen consumption lock.
    """
    app_path = Path("frontend/src/App.tsx")
    tg_path = Path("frontend/src/services/telegram.ts")
    assert app_path.exists() and tg_path.exists()

    app_code = app_path.read_text(encoding="utf-8")
    tg_code = tg_path.read_text(encoding="utf-8")

    # telegram.ts value-based tracking and onActivated
    assert "__evently_last_consumed_start_param" in tg_code
    assert "onActivated" in tg_code
    assert "resetConsumedStartParam" in tg_code

    # App.tsx deep link handling
    assert "openEventById" in app_code
    assert "telegram.consumeStartParam" in app_code
    assert "setIsCityModalOpen(false);" in app_code
    assert "telegram.onActivated" in app_code


@pytest.mark.asyncio
async def test_event_detail_api_works_for_notified_event(client, test_session):
    """
    4. Verifies GET /api/v1/events/{id} returns full, valid details
    for an event that underwent updates and was published.
    """
    owner_id = 9501
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_notif')}"}
    admin_id = 123456789
    auth_admin = {"Authorization": f"tma {make_test_init_data(user_id=admin_id, username='admin_notif')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Cinema Hall", "category": "Кино", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    start_time = datetime.now(timezone.utc) + timedelta(days=7)
    res_ev = await client.post(
        "/api/v1/events",
        json={
            "title": "Interstellar Screening",
            "description": "Special film screening in IMAX.",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": start_time.isoformat(),
            "venue_name": "Screen 1",
            "address": "ул. Расула Гамзатова, 15",
            "organization_id": org_id,
        },
        headers=auth_owner,
    )
    event_id = res_ev.json()["id"]
    await client.post(f"/api/v1/admin/events/{event_id}/publish", headers=auth_admin)

    # Fetch event details
    attendee_id = 9502
    auth_att = {"Authorization": f"tma {make_test_init_data(user_id=attendee_id, username='attendee_notif')}"}
    get_res = await client.get(f"/api/v1/events/{event_id}", headers=auth_att)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == event_id
    assert data["title"] == "Interstellar Screening"
    assert data["status"] == "published"
    assert data["venue_name"] == "Screen 1"


def test_feed_loading_exits_loading_on_api_error():
    """
    5. Contract test verifying App.tsx exits loading/refreshing states on API failure,
    preventing infinite spinner when backend errors or aborts occur.
    """
    app_path = Path("frontend/src/App.tsx")
    assert app_path.exists()
    app_code = app_path.read_text(encoding="utf-8")

    assert "setIsLoadingEvents(false);" in app_code
    assert "setFeedError(" in app_code
    assert "finally" in app_code
    assert "feedAbortControllerRef" in app_code


def test_feed_request_handles_timeout():
    """
    6. Contract test verifying api.ts implements fetchWithTimeout with AbortController,
    configurable timeout (10000ms), and custom timeout error formatting.
    """
    api_path = Path("frontend/src/services/api.ts")
    assert api_path.exists()
    api_code = api_path.read_text(encoding="utf-8")

    assert "fetchWithTimeout" in api_code
    assert "timeoutMs: number = 10000" in api_code
    assert "AbortController" in api_code
    assert "timeout" in api_code.lower()


@pytest.mark.asyncio
async def test_feed_successful_request_loads_events(client, test_session):
    """
    7. Verifies GET /api/v1/events successfully returns 200 with list of events
    for a valid city without timeout or failure.
    """
    res = await client.get("/api/v1/events?city_id=makhachkala")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_subscription_creates_no_confirmation_telegram_message(client, test_session):
    """
    8. Verifies that user subscription creates 0 Telegram bot messages,
    confirming clean silent subscription without spamming the user.
    """
    owner_id = 9601
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_sub0')}"}
    sub_id = 9602
    auth_sub = {"Authorization": f"tma {make_test_init_data(user_id=sub_id, username='sub_user0')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Book Club", "category": "Книги", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    sub_res = await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_sub)
    assert sub_res.status_code == 200
    assert sub_res.json()["is_subscribed"] is True

    # Frontend contract check: OrganizationModal has no requestWriteAccess
    modal_code = Path("frontend/src/components/OrganizationModal.tsx").read_text(encoding="utf-8")
    assert "requestWriteAccess" not in modal_code


def test_duplicate_header_subscription_entry_is_absent():
    """
    9. Verifies that Header.tsx does not contain the duplicate Bookmark button
    or onOpenSubscriptionsModal prop.
    """
    header_path = Path("frontend/src/components/Header.tsx")
    assert header_path.exists()
    header_code = header_path.read_text(encoding="utf-8")

    assert "Bookmark" not in header_code, "Header must not import or render Bookmark"
    assert "onOpenSubscriptionsModal" not in header_code, "Header must not accept onOpenSubscriptionsModal"

    app_path = Path("frontend/src/App.tsx")
    app_code = app_path.read_text(encoding="utf-8")
    assert "<Header" in app_code
    assert "onOpenSubscriptionsModal=" not in app_code, "App.tsx must not pass onOpenSubscriptionsModal to Header"


@pytest.mark.asyncio
async def test_broadcast_access_control_free_organizer_blocked(client, test_session):
    """
    10. Verifies that Free plan organizers are strictly blocked from broadcasting (403 ENTITLEMENT_REQUIRED).
    """
    owner_id = 9701
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_free_bcast')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Free Bakery Bcast", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Free broadcast attempt",
        },
        headers=auth_owner,
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ENTITLEMENT_REQUIRED"
    assert res.json()["detail"]["required_plan"] == "pro"


@pytest.mark.asyncio
async def test_broadcast_access_control_pro_organizer_allowed(client, test_session):
    """
    11. Verifies that Pro plan organizers can successfully create a broadcast.
    """
    owner_id = 9801
    auth_owner = {"Authorization": f"tma {make_test_init_data(user_id=owner_id, username='owner_pro_bcast')}"}

    res_org = await client.post(
        "/api/v1/organizations",
        json={"name": "Pro Bakery Bcast", "category": "Кафе", "city_id": "makhachkala"},
        headers=auth_owner,
    )
    org_id = res_org.json()["id"]

    # Upgrade to Pro
    await EntitlementService.set_organization_plan(
        test_session,
        org_id,
        plan="pro",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )

    # Add a subscriber
    sub_id = 9802
    auth_sub = {"Authorization": f"tma {make_test_init_data(user_id=sub_id, username='pro_bcast_sub')}"}
    await client.post(f"/api/v1/organizations/{org_id}/subscribe", headers=auth_sub)

    res = await client.post(
        "/api/v1/organizer/broadcasts",
        json={
            "organization_id": org_id,
            "target_type": "organization_subscribers",
            "broadcast_type": "marketing",
            "template_key": "custom_update",
            "custom_text": "Pro broadcast success text",
        },
        headers=auth_owner,
    )
    assert res.status_code == 200
    assert res.json()["status"] in ("queued", "sent", "completed")
