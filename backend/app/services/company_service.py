import logging
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.event import Event, EventStatus
from app.models.user import User
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.company import EventCompanyProfile, EventCompanyRequest, EventCompanyMatch
from app.schemas.company import (
    CompanyStatusResponse,
    CompanyMemberItem,
    CompanyRequestItem,
    CompanyRequestsResponse,
    CompanyMatchItem,
)
from app.services.notification_service import notify_company_request

logger = logging.getLogger("evently.company_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def get_company_status(
    session: AsyncSession,
    event_id: str,
    user_id: Optional[int] = None
) -> CompanyStatusResponse:
    """
    Returns aggregate company search status for the event and authenticated user's state.
    Count queries are aggregate subqueries (zero N+1).
    """
    # 1. Check event exists
    event_exists = await session.execute(
        select(Event.id).where(Event.id == event_id, Event.status == EventStatus.PUBLISHED.value)
    )
    if not event_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Событие '{event_id}' не найдено или не опубликовано"
        )

    # 2. Count active company seekers for this event
    active_members_stmt = select(func.count(EventCompanyProfile.id)).where(
        EventCompanyProfile.event_id == event_id,
        EventCompanyProfile.is_active == True
    )
    active_count = (await session.execute(active_members_stmt)).scalar() or 0

    if not user_id:
        return CompanyStatusResponse(
            event_id=event_id,
            is_opted_in=False,
            is_active=False,
            note=None,
            active_members_count=active_count,
            pending_incoming_count=0,
            matches_count=0
        )

    # 3. User's company profile
    prof_stmt = select(EventCompanyProfile).where(
        EventCompanyProfile.event_id == event_id,
        EventCompanyProfile.user_id == user_id
    )
    prof = (await session.execute(prof_stmt)).scalar_one_or_none()

    # 4. User's pending incoming requests count
    incoming_stmt = select(func.count(EventCompanyRequest.id)).where(
        EventCompanyRequest.event_id == event_id,
        EventCompanyRequest.receiver_id == user_id,
        EventCompanyRequest.status == "pending"
    )
    incoming_count = (await session.execute(incoming_stmt)).scalar() or 0

    # 5. User's matches count
    matches_stmt = select(func.count(EventCompanyMatch.id)).where(
        EventCompanyMatch.event_id == event_id,
        or_(EventCompanyMatch.user1_id == user_id, EventCompanyMatch.user2_id == user_id)
    )
    matches_count = (await session.execute(matches_stmt)).scalar() or 0

    return CompanyStatusResponse(
        event_id=event_id,
        is_opted_in=bool(prof),
        is_active=bool(prof and prof.is_active),
        note=prof.note if prof else None,
        active_members_count=active_count,
        pending_incoming_count=incoming_count,
        matches_count=matches_count
    )


async def set_company_profile(
    session: AsyncSession,
    event_id: str,
    user: User,
    is_active: bool = True,
    note: Optional[str] = None
) -> Tuple[EventCompanyProfile, CompanyStatusResponse]:
    """
    Opt-in or update company discovery profile for an event.
    Requires that the user is participating (interest or attending).
    """
    # 1. Check event exists and published
    event = (await session.execute(
        select(Event).where(Event.id == event_id, Event.status == EventStatus.PUBLISHED.value)
    )).scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Событие '{event_id}' не найдено или не опубликовано"
        )

    if is_active and event.start_at < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Мероприятие уже завершено. Поиск компании недоступен."
        )

    # 2. Check event participation rule
    if is_active:
        has_interest = (await session.execute(
            select(EventInterest.id).where(EventInterest.event_id == event_id, EventInterest.user_id == user.id)
        )).scalar_one_or_none()

        has_rsvp = (await session.execute(
            select(EventAttendee.event_id).where(EventAttendee.event_id == event_id, EventAttendee.user_id == user.id)
        )).scalar_one_or_none()

        if not has_interest and not has_rsvp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для поиска компании необходимо выразить интерес («Хочу пойти») или подтвердить участие («Я иду»)"
            )

    # 3. Upsert profile
    prof_stmt = select(EventCompanyProfile).where(
        EventCompanyProfile.event_id == event_id,
        EventCompanyProfile.user_id == user.id
    )
    profile = (await session.execute(prof_stmt)).scalar_one_or_none()

    if profile:
        profile.is_active = is_active
        profile.note = note
        profile.updated_at = utc_now()
    else:
        profile = EventCompanyProfile(
            event_id=event_id,
            user_id=user.id,
            is_active=is_active,
            note=note
        )
        session.add(profile)

    await session.commit()
    await session.refresh(profile)

    status_resp = await get_company_status(session, event_id, user.id)
    return profile, status_resp


async def deactivate_company_profile(
    session: AsyncSession,
    event_id: str,
    user_id: int
) -> CompanyStatusResponse:
    """
    Opt-out: disables company profile visibility for this event without deleting match history.
    Also auto-cancels lingering pending requests involving this user for this event.
    """
    prof_stmt = select(EventCompanyProfile).where(
        EventCompanyProfile.event_id == event_id,
        EventCompanyProfile.user_id == user_id
    )
    profile = (await session.execute(prof_stmt)).scalar_one_or_none()
    if profile:
        profile.is_active = False
        profile.updated_at = utc_now()

    # Cancel pending requests involving this user for this event
    pending_stmt = select(EventCompanyRequest).where(
        EventCompanyRequest.event_id == event_id,
        EventCompanyRequest.status == "pending",
        or_(
            EventCompanyRequest.sender_id == user_id,
            EventCompanyRequest.receiver_id == user_id
        )
    )
    pending_reqs = (await session.execute(pending_stmt)).scalars().all()
    for pr in pending_reqs:
        pr.status = "cancelled"
        pr.updated_at = utc_now()

    await session.commit()
    return await get_company_status(session, event_id, user_id)


async def list_company_members(
    session: AsyncSession,
    event_id: str,
    current_user_id: int,
    limit: int = 20,
    offset: int = 0
) -> List[CompanyMemberItem]:
    """
    Lists active company seekers for this event, excluding current user.
    Pagination: default limit=20, max=50.
    Strict privacy: NO telegram_id, NO username, NO joined_at.
    Zero N+1: batch resolves attendance and relationship status.
    """
    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    # Verify event exists
    event_exists = (await session.execute(
        select(Event.id).where(Event.id == event_id, Event.status == EventStatus.PUBLISHED.value)
    )).scalar_one_or_none()
    if not event_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Событие '{event_id}' не найдено"
        )

    # 1. Fetch active company profiles
    profiles_stmt = (
        select(EventCompanyProfile, User)
        .join(User, EventCompanyProfile.user_id == User.id)
        .where(
            EventCompanyProfile.event_id == event_id,
            EventCompanyProfile.is_active == True,
            EventCompanyProfile.user_id != current_user_id
        )
        .order_by(EventCompanyProfile.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(profiles_stmt)
    rows = res.all()

    if not rows:
        return []

    other_user_ids = [u.id for _, u in rows]

    # 2. Bulk resolve attendance status (attending vs interested)
    attending_stmt = select(EventAttendee.user_id).where(
        EventAttendee.event_id == event_id,
        EventAttendee.user_id.in_(other_user_ids)
    )
    attending_ids = set((await session.execute(attending_stmt)).scalars().all())

    # 3. Bulk resolve existing matches with current_user
    matches_stmt = select(EventCompanyMatch).where(
        EventCompanyMatch.event_id == event_id,
        or_(
            and_(EventCompanyMatch.user1_id == current_user_id, EventCompanyMatch.user2_id.in_(other_user_ids)),
            and_(EventCompanyMatch.user2_id == current_user_id, EventCompanyMatch.user1_id.in_(other_user_ids))
        )
    )
    matched_rows = (await session.execute(matches_stmt)).scalars().all()
    matched_user_ids = set()
    for m in matched_rows:
        matched_user_ids.add(m.user2_id if m.user1_id == current_user_id else m.user1_id)

    # 4. Bulk resolve requests between current_user and other_users
    reqs_stmt = select(EventCompanyRequest).where(
        EventCompanyRequest.event_id == event_id,
        or_(
            and_(EventCompanyRequest.sender_id == current_user_id, EventCompanyRequest.receiver_id.in_(other_user_ids)),
            and_(EventCompanyRequest.receiver_id == current_user_id, EventCompanyRequest.sender_id.in_(other_user_ids))
        )
    )
    reqs_rows = (await session.execute(reqs_stmt)).scalars().all()
    outgoing_pending = set()
    incoming_pending = set()
    for r in reqs_rows:
        if r.status == "pending":
            if r.sender_id == current_user_id:
                outgoing_pending.add(r.receiver_id)
            elif r.receiver_id == current_user_id:
                incoming_pending.add(r.sender_id)

    # 5. Assemble items
    items: List[CompanyMemberItem] = []
    for prof, u in rows:
        att_status = "attending" if u.id in attending_ids else "interested"
        if u.id in matched_user_ids:
            rel_status = "matched"
        elif u.id in outgoing_pending:
            rel_status = "pending_outgoing"
        elif u.id in incoming_pending:
            rel_status = "pending_incoming"
        else:
            rel_status = "none"

        dname = f"{u.first_name} {u.last_name}".strip() if (u.first_name and u.last_name) else (u.first_name or "Участник")

        items.append(
            CompanyMemberItem(
                profile_id=prof.id,
                display_name=dname,
                first_name=u.first_name or "Участник",
                avatar_url=u.avatar_url,
                attendance_status=att_status,
                note=prof.note,
                relationship_status=rel_status
            )
        )

    return items


async def create_company_request(
    session: AsyncSession,
    event_id: str,
    sender: User,
    target_profile_id: Optional[str] = None,
    target_user_id: Optional[int] = None,
    http_client: Optional[httpx.AsyncClient] = None
) -> Tuple[EventCompanyRequest, bool, Optional[EventCompanyMatch]]:
    """
    Creates a companion request from sender to target_user or target_profile_id.
    Cross-request auto-accept: if target previously sent a pending request to sender,
    automatically creates Match.
    """
    # 1. Resolve target user and target profile
    target_prof = None
    target_user = None

    if target_profile_id:
        target_prof = (await session.execute(
            select(EventCompanyProfile).where(
                EventCompanyProfile.id == target_profile_id,
                EventCompanyProfile.event_id == event_id,
                EventCompanyProfile.is_active == True
            )
        )).scalar_one_or_none()
        if not target_prof:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь не найден среди ищущих компанию или приостановил поиск"
            )
        target_user = (await session.execute(
            select(User).where(User.id == target_prof.user_id)
        )).scalar_one_or_none()
    elif target_user_id is not None:
        target_user = (await session.execute(
            select(User).where(or_(User.id == target_user_id, User.telegram_id == target_user_id))
        )).scalar_one_or_none()
        if target_user:
            target_prof = (await session.execute(
                select(EventCompanyProfile).where(
                    EventCompanyProfile.event_id == event_id,
                    EventCompanyProfile.user_id == target_user.id,
                    EventCompanyProfile.is_active == True
                )
            )).scalar_one_or_none()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо указать цель запроса (target_profile_id)"
        )

    if not target_user or not target_prof:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь не найден среди ищущих компанию или приостановил поиск"
        )

    resolved_target_id = target_user.id

    # 2. Validation: no self-requests
    if sender.id == resolved_target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отправить запрос на компанию самому себе"
        )

    # 3. Check event exists
    event = (await session.execute(
        select(Event).where(Event.id == event_id, Event.status == EventStatus.PUBLISHED.value)
    )).scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Событие '{event_id}' не найдено или не опубликовано"
        )

    if event.start_at < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Мероприятие уже завершено. Отправка запросов недоступна."
        )

    # 4. Check sender has active profile
    sender_prof = (await session.execute(
        select(EventCompanyProfile).where(
            EventCompanyProfile.event_id == event_id,
            EventCompanyProfile.user_id == sender.id,
            EventCompanyProfile.is_active == True
        )
    )).scalar_one_or_none()
    if not sender_prof:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для отправки запроса вам необходимо включить поиск компании на это событие"
        )

    # 5. Check target user participation rule
    has_target_interest = (await session.execute(
        select(EventInterest.id).where(EventInterest.event_id == event_id, EventInterest.user_id == resolved_target_id)
    )).scalar_one_or_none()
    has_target_rsvp = (await session.execute(
        select(EventAttendee.event_id).where(EventAttendee.event_id == event_id, EventAttendee.user_id == resolved_target_id)
    )).scalar_one_or_none()
    if not has_target_interest and not has_target_rsvp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь не участвует в этом событии"
        )

    # 6. Check if already matched
    u1, u2 = min(sender.id, resolved_target_id), max(sender.id, resolved_target_id)
    existing_match = (await session.execute(
        select(EventCompanyMatch).where(
            EventCompanyMatch.event_id == event_id,
            EventCompanyMatch.user1_id == u1,
            EventCompanyMatch.user2_id == u2
        )
    )).scalar_one_or_none()
    if existing_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже нашли компанию с этим пользователем"
        )

    # 7. Check existing request from sender to target
    existing_req = (await session.execute(
        select(EventCompanyRequest).where(
            EventCompanyRequest.event_id == event_id,
            EventCompanyRequest.sender_id == sender.id,
            EventCompanyRequest.receiver_id == resolved_target_id
        )
    )).scalar_one_or_none()

    if existing_req:
        if existing_req.status == "declined":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Запрос был ранее отклонен пользователем"
            )
        if existing_req.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Запрос уже отправлен и ожидает ответа"
            )
        if existing_req.status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Запрос уже принят"
            )

    # 8. Check max active outgoing requests rate limit (max 10)
    active_req_count = (await session.execute(
        select(func.count(EventCompanyRequest.id)).where(
            EventCompanyRequest.event_id == event_id,
            EventCompanyRequest.sender_id == sender.id,
            EventCompanyRequest.status == "pending"
        )
    )).scalar() or 0
    if active_req_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышен лимит активных запросов (максимум 10 на одно событие)"
        )

    # 9. Cross-Request Auto-Accept check:
    # If target already sent a pending request to sender -> auto-accept to Match!
    inverse_req = (await session.execute(
        select(EventCompanyRequest).where(
            EventCompanyRequest.event_id == event_id,
            EventCompanyRequest.sender_id == resolved_target_id,
            EventCompanyRequest.receiver_id == sender.id,
            EventCompanyRequest.status == "pending"
        )
    )).scalar_one_or_none()

    if inverse_req:
        inverse_req.status = "accepted"
        inverse_req.updated_at = utc_now()

        match = EventCompanyMatch(
            event_id=event_id,
            user1_id=u1,
            user2_id=u2,
            request_id=inverse_req.id
        )
        session.add(match)
        await session.commit()
        await session.refresh(inverse_req)
        await session.refresh(match)
        return inverse_req, True, match

    # 10. Create fresh pending request
    new_req = EventCompanyRequest(
        event_id=event_id,
        sender_id=sender.id,
        receiver_id=resolved_target_id,
        status="pending"
    )
    session.add(new_req)
    await session.commit()
    await session.refresh(new_req)

    # 11. Fire Telegram notification (resilient to errors)
    if target_user.telegram_id:
        try:
            await notify_company_request(
                event_id=event_id,
                event_title=event.title,
                sender_first_name=sender.first_name or "Пользователь Ivently",
                receiver_telegram_id=target_user.telegram_id,
                http_client=http_client
            )
        except Exception as e:
            logger.warning(f"Telegram notification delivery note: {e}")

    return new_req, False, None


async def respond_to_company_request(
    session: AsyncSession,
    event_id: str,
    request_id: str,
    current_user: User,
    action: str  # "accept" or "decline"
) -> Tuple[EventCompanyRequest, Optional[EventCompanyMatch]]:
    """
    Accepts or declines an incoming company request.
    Only receiver can respond.
    """
    if action not in ("accept", "decline"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Действие должно быть 'accept' или 'decline'"
        )

    req = (await session.execute(
        select(EventCompanyRequest).where(
            EventCompanyRequest.id == request_id,
            EventCompanyRequest.event_id == event_id
        )
    )).scalar_one_or_none()

    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запрос не найден"
        )

    if req.receiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет прав на ответ на этот запрос"
        )

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Запрос уже был обработан (текущий статус: {req.status})"
        )

    if action == "accept":
        # Verify both users still have active company profiles
        sender_prof = (await session.execute(
            select(EventCompanyProfile).where(
                EventCompanyProfile.event_id == event_id,
                EventCompanyProfile.user_id == req.sender_id,
                EventCompanyProfile.is_active == True
            )
        )).scalar_one_or_none()
        if not sender_prof:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь, отправивший запрос, приостановил поиск компании"
            )

        receiver_prof = (await session.execute(
            select(EventCompanyProfile).where(
                EventCompanyProfile.event_id == event_id,
                EventCompanyProfile.user_id == req.receiver_id,
                EventCompanyProfile.is_active == True
            )
        )).scalar_one_or_none()
        if not receiver_prof:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для ответа на запрос необходимо включить поиск компании"
            )

        req.status = "accepted"
        req.updated_at = utc_now()

        u1, u2 = min(req.sender_id, req.receiver_id), max(req.sender_id, req.receiver_id)
        # Check if match already exists
        match = (await session.execute(
            select(EventCompanyMatch).where(
                EventCompanyMatch.event_id == event_id,
                EventCompanyMatch.user1_id == u1,
                EventCompanyMatch.user2_id == u2
            )
        )).scalar_one_or_none()

        if not match:
            match = EventCompanyMatch(
                event_id=event_id,
                user1_id=u1,
                user2_id=u2,
                request_id=req.id
            )
            session.add(match)

        await session.commit()
        await session.refresh(req)
        await session.refresh(match)
        return req, match

    elif action == "decline":
        req.status = "declined"
        req.updated_at = utc_now()
        await session.commit()
        await session.refresh(req)
        return req, None


async def cancel_company_request(
    session: AsyncSession,
    event_id: str,
    request_id: str,
    current_user_id: int
) -> EventCompanyRequest:
    """
    Cancels an outgoing company request. Only sender can cancel.
    """
    req = (await session.execute(
        select(EventCompanyRequest).where(
            EventCompanyRequest.id == request_id,
            EventCompanyRequest.event_id == event_id
        )
    )).scalar_one_or_none()

    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запрос не найден"
        )

    if req.sender_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы можете отменить только свой исходящий запрос"
        )

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Нельзя отменить запрос в статусе '{req.status}'"
        )

    req.status = "cancelled"
    req.updated_at = utc_now()
    await session.commit()
    await session.refresh(req)
    return req


async def list_requests(
    session: AsyncSession,
    event_id: str,
    current_user_id: int
) -> CompanyRequestsResponse:
    """
    Returns incoming and outgoing requests for the current user and event.
    Strict privacy: username is NEVER included before match!
    """
    # Verify event exists and is published
    event_exists = (await session.execute(
        select(Event.id).where(Event.id == event_id, Event.status == EventStatus.PUBLISHED.value)
    )).scalar_one_or_none()
    if not event_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Событие '{event_id}' не найдено или не опубликовано"
        )

    # 1. Incoming requests
    incoming_stmt = (
        select(EventCompanyRequest, User, EventCompanyProfile.note)
        .join(User, EventCompanyRequest.sender_id == User.id)
        .outerjoin(
            EventCompanyProfile,
            and_(EventCompanyProfile.event_id == event_id, EventCompanyProfile.user_id == User.id)
        )
        .where(
            EventCompanyRequest.event_id == event_id,
            EventCompanyRequest.receiver_id == current_user_id,
            EventCompanyRequest.status == "pending"
        )
        .order_by(EventCompanyRequest.created_at.desc())
    )
    incoming_rows = (await session.execute(incoming_stmt)).all()

    # 2. Outgoing requests
    outgoing_stmt = (
        select(EventCompanyRequest, User, EventCompanyProfile.note)
        .join(User, EventCompanyRequest.receiver_id == User.id)
        .outerjoin(
            EventCompanyProfile,
            and_(EventCompanyProfile.event_id == event_id, EventCompanyProfile.user_id == User.id)
        )
        .where(
            EventCompanyRequest.event_id == event_id,
            EventCompanyRequest.sender_id == current_user_id
        )
        .order_by(EventCompanyRequest.created_at.desc())
    )
    outgoing_rows = (await session.execute(outgoing_stmt)).all()

    # Bulk collect user IDs to determine attendance status
    all_other_ids = [u.id for _, u, _ in incoming_rows] + [u.id for _, u, _ in outgoing_rows]
    attending_ids = set()
    if all_other_ids:
        att_stmt = select(EventAttendee.user_id).where(
            EventAttendee.event_id == event_id,
            EventAttendee.user_id.in_(all_other_ids)
        )
        attending_ids = set((await session.execute(att_stmt)).scalars().all())

    incoming_items = [
        CompanyRequestItem(
            request_id=req.id,
            event_id=event_id,
            other_user_id=u.id,
            other_first_name=u.first_name or "Участник",
            other_user_display_name=f"{u.first_name} {u.last_name}".strip() if (u.first_name and u.last_name) else (u.first_name or "Участник"),
            other_avatar_url=u.avatar_url,
            other_attendance_status="attending" if u.id in attending_ids else "interested",
            note=note,
            direction="incoming",
            status=req.status,
            created_at=req.created_at
        )
        for req, u, note in incoming_rows
    ]

    outgoing_items = [
        CompanyRequestItem(
            request_id=req.id,
            event_id=event_id,
            other_user_id=u.id,
            other_first_name=u.first_name or "Участник",
            other_user_display_name=f"{u.first_name} {u.last_name}".strip() if (u.first_name and u.last_name) else (u.first_name or "Участник"),
            other_avatar_url=u.avatar_url,
            other_attendance_status="attending" if u.id in attending_ids else "interested",
            note=note,
            direction="outgoing",
            status=req.status,
            created_at=req.created_at
        )
        for req, u, note in outgoing_rows
    ]

    return CompanyRequestsResponse(incoming=incoming_items, outgoing=outgoing_items)


async def list_matches(
    session: AsyncSession,
    event_id: str,
    current_user_id: int
) -> List[CompanyMatchItem]:
    """
    Returns mutual matches for current user and event.
    Telegram @username is revealed ONLY here.
    """
    # Verify event exists and is published
    event_exists = (await session.execute(
        select(Event.id).where(Event.id == event_id, Event.status == EventStatus.PUBLISHED.value)
    )).scalar_one_or_none()
    if not event_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Событие '{event_id}' не найдено или не опубликовано"
        )

    matches_stmt = select(EventCompanyMatch).where(
        EventCompanyMatch.event_id == event_id,
        or_(
            EventCompanyMatch.user1_id == current_user_id,
            EventCompanyMatch.user2_id == current_user_id
        )
    ).order_by(EventCompanyMatch.created_at.desc())

    matches = (await session.execute(matches_stmt)).scalars().all()
    if not matches:
        return []

    partner_ids = [
        m.user2_id if m.user1_id == current_user_id else m.user1_id
        for m in matches
    ]

    # Bulk load partner users
    users_stmt = select(User).where(User.id.in_(partner_ids))
    partners = {u.id: u for u in (await session.execute(users_stmt)).scalars().all()}

    # Bulk load attendance status
    att_stmt = select(EventAttendee.user_id).where(
        EventAttendee.event_id == event_id,
        EventAttendee.user_id.in_(partner_ids)
    )
    attending_ids = set((await session.execute(att_stmt)).scalars().all())

    items: List[CompanyMatchItem] = []
    for m in matches:
        pid = m.user2_id if m.user1_id == current_user_id else m.user1_id
        partner = partners.get(pid)
        if not partner:
            continue

        raw_uname = (partner.username or "").strip().lstrip("@")
        telegram_url = f"https://t.me/{raw_uname}" if raw_uname else None
        partner_dname = f"{partner.first_name} {partner.last_name}".strip() if (partner.first_name and partner.last_name) else (partner.first_name or "Участник")
        att_status = "attending" if partner.id in attending_ids else "interested"

        items.append(
            CompanyMatchItem(
                match_id=m.id,
                event_id=event_id,
                partner_id=partner.id,
                partner_first_name=partner.first_name or "Участник",
                partner_display_name=partner_dname,
                partner_avatar_url=partner.avatar_url,
                partner_attendance_status=att_status,
                attendance_status=att_status,
                partner_telegram_username=raw_uname if raw_uname else None,
                partner_telegram_url=telegram_url,
                has_telegram_username=bool(raw_uname),
                matched_at=m.created_at
            )
        )

    return items


async def auto_deactivate_profile_if_not_participating(
    session: AsyncSession,
    event_id: str,
    user_id: int
) -> None:
    """
    Hook called when user cancels RSVP or Interest.
    If the user has NEITHER interest NOR attendance, their company profile is auto-disabled.
    Also auto-cancels lingering pending requests involving this user for this event.
    """
    has_interest = (await session.execute(
        select(EventInterest.id).where(
            EventInterest.event_id == event_id,
            EventInterest.user_id == user_id
        )
    )).scalar_one_or_none()

    has_rsvp = (await session.execute(
        select(EventAttendee.event_id).where(
            EventAttendee.event_id == event_id,
            EventAttendee.user_id == user_id
        )
    )).scalar_one_or_none()

    if not has_interest and not has_rsvp:
        prof = (await session.execute(
            select(EventCompanyProfile).where(
                EventCompanyProfile.event_id == event_id,
                EventCompanyProfile.user_id == user_id,
                EventCompanyProfile.is_active == True
            )
        )).scalar_one_or_none()
        if prof:
            prof.is_active = False
            prof.updated_at = utc_now()

            # Cancel pending requests involving this user for this event
            pending_stmt = select(EventCompanyRequest).where(
                EventCompanyRequest.event_id == event_id,
                EventCompanyRequest.status == "pending",
                or_(
                    EventCompanyRequest.sender_id == user_id,
                    EventCompanyRequest.receiver_id == user_id
                )
            )
            pending_reqs = (await session.execute(pending_stmt)).scalars().all()
            for pr in pending_reqs:
                pr.status = "cancelled"
                pr.updated_at = utc_now()

            await session.commit()
            logger.info(f"Auto-deactivated company profile and cancelled pending requests for user {user_id} on event {event_id} due to lack of participation.")
