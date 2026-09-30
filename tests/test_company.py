import pytest
from sqlalchemy import select, func
from app.models.event import Event
from app.models.company import EventCompanyProfile, EventCompanyRequest, EventCompanyMatch
from app.models.interest import EventInterest
from app.models.attendee import EventAttendee
from app.services.event_service import list_published_events, add_event_interest, remove_event_interest
from conftest import make_test_init_data


@pytest.mark.asyncio
async def test_company_status_endpoint(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    # 1. Unauthenticated GET /status -> returns active_members_count only
    res_unauth = await client.get(f"/api/v1/events/{event_id}/company/status")
    assert res_unauth.status_code == 200
    data = res_unauth.json()
    assert data["event_id"] == event_id
    assert data["is_opted_in"] is False
    assert data["is_active"] is False
    assert "active_members_count" in data

    # 2. Authenticated user without opt-in
    headers = {"Authorization": f"tma {make_test_init_data(user_id=10101)}"}
    res_auth = await client.get(f"/api/v1/events/{event_id}/company/status", headers=headers)
    assert res_auth.status_code == 200
    assert res_auth.json()["is_opted_in"] is False


@pytest.mark.asyncio
async def test_opt_in_requires_participation_and_opt_out(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id
    headers = {"Authorization": f"tma {make_test_init_data(user_id=10102)}"}

    # 1. User without interest or RSVP tries to opt-in -> 400
    res_optin_fail = await client.post(
        f"/api/v1/events/{event_id}/company/profile",
        json={"is_active": True, "note": "Ищу компанию на вечер"},
        headers=headers
    )
    assert res_optin_fail.status_code == 400
    assert "необходимо выразить интерес" in res_optin_fail.json()["detail"].lower()

    # 2. Mark interest
    res_int = await client.post(f"/api/v1/events/{event_id}/interest", headers=headers)
    assert res_int.status_code == 200

    # 3. Now opt-in succeeds
    res_optin = await client.post(
        f"/api/v1/events/{event_id}/company/profile",
        json={"is_active": True, "note": "Ищу компанию на концерт"},
        headers=headers
    )
    assert res_optin.status_code == 200
    opt_data = res_optin.json()
    assert opt_data["is_opted_in"] is True
    assert opt_data["is_active"] is True
    assert opt_data["note"] == "Ищу компанию на концерт"
    assert opt_data["active_members_count"] >= 1

    # 4. Opt-out via DELETE /profile -> sets is_active=False
    res_optout = await client.delete(f"/api/v1/events/{event_id}/company/profile", headers=headers)
    assert res_optout.status_code == 200
    assert res_optout.json()["is_active"] is False


async def get_user_id(client, headers) -> int:
    res = await client.get("/api/v1/users/me", headers=headers)
    return res.json()["id"]


@pytest.mark.asyncio
async def test_members_list_privacy(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    # User A (9901) and User B (9902)
    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=9901, username='user_a_private')}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=9902, username='user_b_private')}"}

    user_a_id = await get_user_id(client, headers_a)
    user_b_id = await get_user_id(client, headers_b)

    # User A: interest + opt-in
    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_a)
    await client.post(
        f"/api/v1/events/{event_id}/company/profile",
        json={"is_active": True, "note": "Заметка от А"},
        headers=headers_a
    )

    # User B: interest + opt-in
    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_b)
    await client.post(
        f"/api/v1/events/{event_id}/company/profile",
        json={"is_active": True, "note": "Заметка от Б"},
        headers=headers_b
    )

    # User A fetches /members
    res_members = await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)
    assert res_members.status_code == 200
    members = res_members.json()

    # User A must NOT see themselves
    assert not any(m["note"] == "Заметка от А" for m in members)

    # User B must be visible
    target = next((m for m in members if m["note"] == "Заметка от Б"), None)
    assert target is not None
    assert target["note"] == "Заметка от Б"
    assert target["attendance_status"] == "interested"
    assert target["relationship_status"] == "none"

    # STRICT PRIVACY: verify internal user_id, username, telegram_id, joined_at are NOT present!
    assert "user_id" not in target
    assert "profile_id" in target
    assert isinstance(target["profile_id"], str)
    assert "username" not in target
    assert "telegram_username" not in target
    assert "telegram_id" not in target
    assert "joined_at" not in target


@pytest.mark.asyncio
async def test_requests_and_cross_request_auto_match(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    # User X (8801) and User Y (8802)
    headers_x = {"Authorization": f"tma {make_test_init_data(user_id=8801, username='alex_x')}"}
    headers_y = {"Authorization": f"tma {make_test_init_data(user_id=8802, username='elena_y')}"}

    user_x_id = await get_user_id(client, headers_x)
    user_y_id = await get_user_id(client, headers_y)

    # Setup profiles
    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_x)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_x)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_y)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_y)

    # 1. User X self-request -> 400
    res_self = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_user_id": user_x_id},
        headers=headers_x
    )
    assert res_self.status_code == 400

    # 2. User X sends request to User Y -> pending
    res_req = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_user_id": user_y_id},
        headers=headers_x
    )
    assert res_req.status_code == 200
    assert res_req.json()["match_created"] is False
    assert "отправлен" in res_req.json()["message"].lower()

    # 3. Duplicate request from X to Y -> 400
    res_dup = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_user_id": user_y_id},
        headers=headers_x
    )
    assert res_dup.status_code == 400

    # 4. Check requests list
    # User X sees outgoing request
    res_x_reqs = await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_x)
    assert res_x_reqs.status_code == 200
    out_items = res_x_reqs.json()["outgoing"]
    assert any(r["other_user_id"] == user_y_id and r["status"] == "pending" for r in out_items)

    # User Y sees incoming request
    res_y_reqs = await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_y)
    assert res_y_reqs.status_code == 200
    in_items = res_y_reqs.json()["incoming"]
    assert any(r["other_user_id"] == user_x_id for r in in_items)

    # 5. Cross-Request Auto-Accept: User Y sends request to User X
    # Must immediately detect existing request and auto-create Match!
    res_cross = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_user_id": user_x_id},
        headers=headers_y
    )
    assert res_cross.status_code == 200
    cross_data = res_cross.json()
    assert cross_data["match_created"] is True
    assert cross_data["match"] is not None

    # 6. Verify Telegram username revealed in GET /matches for both users
    res_x_matches = await client.get(f"/api/v1/events/{event_id}/company/matches", headers=headers_x)
    assert res_x_matches.status_code == 200
    x_matches = res_x_matches.json()
    assert len(x_matches) >= 1
    match_with_y = next(m for m in x_matches if m["partner_id"] == user_y_id)
    assert match_with_y["partner_telegram_username"] == "elena_y"
    assert match_with_y["partner_telegram_url"] == "https://t.me/elena_y"
    assert match_with_y["has_telegram_username"] is True

    res_y_matches = await client.get(f"/api/v1/events/{event_id}/company/matches", headers=headers_y)
    assert res_y_matches.status_code == 200
    y_matches = res_y_matches.json()
    match_with_x = next(m for m in y_matches if m["partner_id"] == user_x_id)
    assert match_with_x["partner_telegram_username"] == "alex_x"
    assert match_with_x["partner_telegram_url"] == "https://t.me/alex_x"


@pytest.mark.asyncio
async def test_manual_accept_and_decline(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    # User 1 (7701) and User 2 (7702)
    headers_1 = {"Authorization": f"tma {make_test_init_data(user_id=7701, username='user_one')}"}
    headers_2 = {"Authorization": f"tma {make_test_init_data(user_id=7702, username='user_two')}"}

    user_1_id = await get_user_id(client, headers_1)
    user_2_id = await get_user_id(client, headers_2)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_1)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_1)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_2)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_2)

    # 1. User 1 sends request to User 2
    res_req = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_user_id": user_2_id},
        headers=headers_1
    )
    assert res_req.status_code == 200

    # User 2 gets incoming requests
    reqs = (await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_2)).json()["incoming"]
    request_id = next(r["request_id"] for r in reqs if r["other_user_id"] == user_1_id)

    # 2. User 1 (sender) tries to accept -> 403 Forbidden
    res_hack = await client.post(
        f"/api/v1/events/{event_id}/company/requests/{request_id}/accept",
        headers=headers_1
    )
    assert res_hack.status_code == 403

    # 3. User 2 (receiver) accepts -> 200, Match created
    res_accept = await client.post(
        f"/api/v1/events/{event_id}/company/requests/{request_id}/accept",
        headers=headers_2
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["match_created"] is True
    assert res_accept.json()["match"]["partner_telegram_username"] == "user_one"

    # 4. Repeated accept -> 400
    res_rep = await client.post(
        f"/api/v1/events/{event_id}/company/requests/{request_id}/accept",
        headers=headers_2
    )
    assert res_rep.status_code == 400

    # 5. Decline test: User 3 (7703) -> User 4 (7704)
    headers_3 = {"Authorization": f"tma {make_test_init_data(user_id=7703)}"}
    headers_4 = {"Authorization": f"tma {make_test_init_data(user_id=7704)}"}

    user_3_id = await get_user_id(client, headers_3)
    user_4_id = await get_user_id(client, headers_4)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_3)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_3)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_4)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_4)

    await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_user_id": user_4_id}, headers=headers_3)
    reqs_4 = (await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_4)).json()["incoming"]
    req_id_34 = next(r["request_id"] for r in reqs_4 if r["other_user_id"] == user_3_id)

    # User 4 declines
    res_dec = await client.post(
        f"/api/v1/events/{event_id}/company/requests/{req_id_34}/decline",
        headers=headers_4
    )
    assert res_dec.status_code == 200

    # User 3 tries to send again -> 400 (cannot re-send after decline)
    res_re_send = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_user_id": user_4_id},
        headers=headers_3
    )
    assert res_re_send.status_code == 400


@pytest.mark.asyncio
async def test_cancel_outgoing_request(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=6601)}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=6602)}"}

    user_a_id = await get_user_id(client, headers_a)
    user_b_id = await get_user_id(client, headers_b)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_a)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_a)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_b)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_b)

    await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_user_id": user_b_id}, headers=headers_a)

    reqs_a = (await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_a)).json()["outgoing"]
    req_id = next(r["request_id"] for r in reqs_a if r["other_user_id"] == user_b_id)

    # User B tries to cancel A's request -> 403
    res_cancel_b = await client.delete(f"/api/v1/events/{event_id}/company/requests/{req_id}", headers=headers_b)
    assert res_cancel_b.status_code == 403

    # User A cancels their own request -> 200
    res_cancel_a = await client.delete(f"/api/v1/events/{event_id}/company/requests/{req_id}", headers=headers_a)
    assert res_cancel_a.status_code == 200


@pytest.mark.asyncio
async def test_participation_loss_auto_deactivates_company_profile(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id
    headers = {"Authorization": f"tma {make_test_init_data(user_id=5501)}"}

    # 1. User sets interest and opts in
    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers)

    status_1 = (await client.get(f"/api/v1/events/{event_id}/company/status", headers=headers)).json()
    assert status_1["is_active"] is True

    # 2. User removes interest (and has no RSVP)
    await client.delete(f"/api/v1/events/{event_id}/interest", headers=headers)

    # 3. Status is_active must automatically become False
    status_2 = (await client.get(f"/api/v1/events/{event_id}/company/status", headers=headers)).json()
    assert status_2["is_active"] is False


@pytest.mark.asyncio
async def test_user_without_telegram_username(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    # User with no username (None)
    headers_no_uname = {"Authorization": f"tma {make_test_init_data(user_id=4401, username=None)}"}
    headers_partner = {"Authorization": f"tma {make_test_init_data(user_id=4402, username='partner_has_uname')}"}

    user_no_uname_id = await get_user_id(client, headers_no_uname)
    user_partner_id = await get_user_id(client, headers_partner)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_no_uname)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_no_uname)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_partner)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_partner)

    # Send request and cross-accept
    await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_user_id": user_partner_id}, headers=headers_no_uname)
    await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_user_id": user_no_uname_id}, headers=headers_partner)

    # Partner inspects match with user who has no username
    matches = (await client.get(f"/api/v1/events/{event_id}/company/matches", headers=headers_partner)).json()
    m = next(item for item in matches if item["partner_id"] == user_no_uname_id)
    assert m["partner_telegram_username"] is None
    assert m["partner_telegram_url"] is None
    assert m["has_telegram_username"] is False


@pytest.mark.asyncio
async def test_company_unauthorized_access(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    # 1. Unauthenticated /members -> 401
    res1 = await client.get(f"/api/v1/events/{event_id}/company/members")
    assert res1.status_code == 401

    # 2. Unauthenticated /requests -> 401
    res2 = await client.get(f"/api/v1/events/{event_id}/company/requests")
    assert res2.status_code == 401

    # 3. Unauthenticated POST /requests -> 401
    res3 = await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_profile_id": "none"})
    assert res3.status_code == 401

    # 4. Unauthenticated /matches -> 401
    res4 = await client.get(f"/api/v1/events/{event_id}/company/matches")
    assert res4.status_code == 401

    # 5. Unauthenticated POST /profile -> 401
    res5 = await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True})
    assert res5.status_code == 401


@pytest.mark.asyncio
async def test_cross_event_request_rejected(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    assert len(events) >= 2
    event_1_id = events[0].id
    event_2_id = events[1].id

    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=3301, username='cross_a')}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=3302, username='cross_b')}"}

    # User A opts in on Event 1
    await client.post(f"/api/v1/events/{event_1_id}/interest", headers=headers_a)
    await client.post(f"/api/v1/events/{event_1_id}/company/profile", json={"is_active": True}, headers=headers_a)

    # User B opts in on Event 2 (NOT Event 1)
    await client.post(f"/api/v1/events/{event_2_id}/interest", headers=headers_b)
    prof_b_res = await client.post(f"/api/v1/events/{event_2_id}/company/profile", json={"is_active": True}, headers=headers_b)
    assert prof_b_res.status_code == 200

    # User B's profile on Event 2
    members_e2 = (await client.get(f"/api/v1/events/{event_2_id}/company/members", headers=headers_a)).json()
    target_prof_e2 = next(m["profile_id"] for m in members_e2 if m["note"] is None)

    # User A tries to send request on Event 1 using User B's profile from Event 2 -> 400 Rejected
    res_cross = await client.post(
        f"/api/v1/events/{event_1_id}/company/requests",
        json={"target_profile_id": target_prof_e2},
        headers=headers_a
    )
    assert res_cross.status_code == 400
    assert "не найден среди ищущих компанию" in res_cross.json()["detail"].lower()


@pytest.mark.asyncio
async def test_request_to_inactive_profile_rejected(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=3201)}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=3202)}"}

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_a)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_a)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_b)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_b)

    members = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)).json()
    b_prof_id = members[0]["profile_id"]

    # User B deactivates profile
    await client.delete(f"/api/v1/events/{event_id}/company/profile", headers=headers_b)

    # User B is no longer in members
    members_after = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)).json()
    assert not any(m["profile_id"] == b_prof_id for m in members_after)

    # User A tries to send request to B's profile -> 400 Rejected
    res_req = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_profile_id": b_prof_id},
        headers=headers_a
    )
    assert res_req.status_code == 400


@pytest.mark.asyncio
async def test_request_using_target_profile_id_and_status(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=3101, username='req_a')}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=3102, username='req_b')}"}

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_a)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True, "note": "Hello from A"}, headers=headers_a)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_b)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True, "note": "Hello from B"}, headers=headers_b)

    # User A views members -> sees B's profile_id
    members_for_a = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)).json()
    b_item = next(m for m in members_for_a if m["note"] == "Hello from B")
    assert b_item["relationship_status"] == "none"
    b_profile_id = b_item["profile_id"]

    # User A sends request using target_profile_id
    res_send = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_profile_id": b_profile_id},
        headers=headers_a
    )
    assert res_send.status_code == 200

    # User A checks members -> B's relationship_status is now "pending_outgoing"
    members_for_a_after = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)).json()
    b_item_after = next(m for m in members_for_a_after if m["note"] == "Hello from B")
    assert b_item_after["relationship_status"] == "pending_outgoing"

    # User B checks members -> A's relationship_status is now "pending_incoming"
    members_for_b = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_b)).json()
    a_item = next(m for m in members_for_b if m["note"] == "Hello from A")
    assert a_item["relationship_status"] == "pending_incoming"


@pytest.mark.asyncio
async def test_rsvp_cancel_keeps_profile_active_if_interest_exists(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id
    headers = {"Authorization": f"tma {make_test_init_data(user_id=3001)}"}
    u_id = await get_user_id(client, headers)

    # User adds RSVP and opts in
    await client.post(f"/api/v1/events/{event_id}/rsvp", headers=headers)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers)

    # Directly ensure EventInterest is also present
    test_session.add(EventInterest(event_id=event_id, user_id=u_id))
    await test_session.commit()

    # Cancel RSVP
    await client.delete(f"/api/v1/events/{event_id}/rsvp", headers=headers)

    # Company profile MUST remain active because Interest still exists
    status = (await client.get(f"/api/v1/events/{event_id}/company/status", headers=headers)).json()
    assert status["is_active"] is True


@pytest.mark.asyncio
async def test_interest_cancel_keeps_profile_active_if_rsvp_exists(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id
    headers = {"Authorization": f"tma {make_test_init_data(user_id=3002)}"}
    u_id = await get_user_id(client, headers)

    # User adds Interest and opts in
    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers)

    # Directly ensure EventAttendee is also present
    test_session.add(EventAttendee(event_id=event_id, user_id=u_id))
    await test_session.commit()

    # Cancel Interest
    await client.delete(f"/api/v1/events/{event_id}/interest", headers=headers)

    # Company profile MUST remain active because RSVP still exists
    status = (await client.get(f"/api/v1/events/{event_id}/company/status", headers=headers)).json()
    assert status["is_active"] is True


@pytest.mark.asyncio
async def test_max_10_outgoing_requests_rate_limit(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_sender = {"Authorization": f"tma {make_test_init_data(user_id=2900)}"}
    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_sender)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_sender)

    # Create 11 target users with active company profiles
    for uid in range(2901, 2912):
        h = {"Authorization": f"tma {make_test_init_data(user_id=uid)}"}
        await client.post(f"/api/v1/events/{event_id}/interest", headers=h)
        await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True, "note": f"User {uid}"}, headers=h)

    # Sender fetches members
    members = (await client.get(f"/api/v1/events/{event_id}/company/members?limit=50", headers=headers_sender)).json()
    t_prof_map = {m["note"]: m["profile_id"] for m in members if m["note"]}

    # Send 10 requests -> all 10 succeed
    for uid in range(2901, 2911):
        pid = t_prof_map[f"User {uid}"]
        res = await client.post(
            f"/api/v1/events/{event_id}/company/requests",
            json={"target_profile_id": pid},
            headers=headers_sender
        )
        assert res.status_code == 200

    # 11th request -> 429 Too Many Requests
    pid_11 = t_prof_map["User 2911"]
    res_11 = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_profile_id": pid_11},
        headers=headers_sender
    )
    assert res_11.status_code == 429
    assert "превышен лимит активных запросов" in res_11.json()["detail"].lower()


@pytest.mark.asyncio
async def test_telegram_notification_failure_resilience(client, test_session, monkeypatch):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=2801)}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=2802)}"}

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_a)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_a)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_b)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_b)

    members = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)).json()
    b_pid = members[0]["profile_id"]

    # Mock notify_company_request to raise an Exception
    async def mock_fail_notify(*args, **kwargs):
        raise RuntimeError("Simulated Telegram Bot API 500 error / timeout")

    monkeypatch.setattr("app.services.company_service.notify_company_request", mock_fail_notify)

    # Request creation MUST still succeed with 200 OK
    res = await client.post(
        f"/api/v1/events/{event_id}/company/requests",
        json={"target_profile_id": b_pid},
        headers=headers_a
    )
    assert res.status_code == 200
    assert "отправлен" in res.json()["message"].lower()


@pytest.mark.asyncio
async def test_match_isolation_between_users(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_1 = {"Authorization": f"tma {make_test_init_data(user_id=2701, username='iso_1')}"}
    headers_2 = {"Authorization": f"tma {make_test_init_data(user_id=2702, username='iso_2')}"}
    headers_3 = {"Authorization": f"tma {make_test_init_data(user_id=2703, username='iso_3')}"}

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_1)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True, "note": "Iso User 1"}, headers=headers_1)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_2)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True, "note": "Iso User 2"}, headers=headers_2)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_3)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True, "note": "Iso User 3"}, headers=headers_3)

    # User 1 sends request to User 2 -> cross-accept
    m1 = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_1)).json()
    u2_pid = next(m["profile_id"] for m in m1 if m["note"] == "Iso User 2")

    # User 1 sends to User 2
    r_send = await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_profile_id": u2_pid}, headers=headers_1)
    assert r_send.status_code == 200

    # User 2 accepts
    reqs_2 = (await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_2)).json()["incoming"]
    await client.post(f"/api/v1/events/{event_id}/company/requests/{reqs_2[0]['request_id']}/accept", headers=headers_2)

    # User 1 and User 2 see match
    matches_1 = (await client.get(f"/api/v1/events/{event_id}/company/matches", headers=headers_1)).json()
    assert len(matches_1) == 1

    # User 3 calls GET /matches -> MUST receive empty list (zero leakage of User 1 & 2 match)
    matches_3 = (await client.get(f"/api/v1/events/{event_id}/company/matches", headers=headers_3)).json()
    assert matches_3 == []


@pytest.mark.asyncio
async def test_cannot_accept_request_if_sender_deactivated_profile(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=2601)}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=2602)}"}

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_a)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_a)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_b)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_b)

    members_a = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)).json()
    b_pid = members_a[0]["profile_id"]

    # User A sends request to User B
    await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_profile_id": b_pid}, headers=headers_a)

    # User B has incoming request
    reqs_b = (await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_b)).json()["incoming"]
    assert len(reqs_b) == 1
    req_id = reqs_b[0]["request_id"]

    # User A deactivates company profile
    await client.delete(f"/api/v1/events/{event_id}/company/profile", headers=headers_a)

    # User B attempts to accept request from deactivated user A -> 400 Rejected
    res_accept = await client.post(
        f"/api/v1/events/{event_id}/company/requests/{req_id}/accept",
        headers=headers_b
    )
    assert res_accept.status_code == 400


@pytest.mark.asyncio
async def test_deactivate_cancels_pending_requests(client, test_session):
    events, _ = await list_published_events(test_session, city_id="spb")
    event_id = events[0].id

    headers_a = {"Authorization": f"tma {make_test_init_data(user_id=2501)}"}
    headers_b = {"Authorization": f"tma {make_test_init_data(user_id=2502)}"}

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_a)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_a)

    await client.post(f"/api/v1/events/{event_id}/interest", headers=headers_b)
    await client.post(f"/api/v1/events/{event_id}/company/profile", json={"is_active": True}, headers=headers_b)

    members_a = (await client.get(f"/api/v1/events/{event_id}/company/members", headers=headers_a)).json()
    b_pid = members_a[0]["profile_id"]

    # User A sends request to User B
    await client.post(f"/api/v1/events/{event_id}/company/requests", json={"target_profile_id": b_pid}, headers=headers_a)

    # User B deactivates their profile
    await client.delete(f"/api/v1/events/{event_id}/company/profile", headers=headers_b)

    # In User A's outgoing requests, the request is now cancelled (no longer pending)
    out_reqs = (await client.get(f"/api/v1/events/{event_id}/company/requests", headers=headers_a)).json()["outgoing"]
    assert len(out_reqs) == 1
    assert out_reqs[0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_nonexistent_or_unpublished_event_rejected(client, test_session):
    headers = {"Authorization": f"tma {make_test_init_data(user_id=2401)}"}
    fake_event_id = "non-existent-event-id"

    # GET /requests on fake event -> 404
    r1 = await client.get(f"/api/v1/events/{fake_event_id}/company/requests", headers=headers)
    assert r1.status_code == 404

    # GET /matches on fake event -> 404
    r2 = await client.get(f"/api/v1/events/{fake_event_id}/company/matches", headers=headers)
    assert r2.status_code == 404

