from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.api.deps import get_current_user, get_current_user_optional
from app.schemas.company import (
    CompanyStatusResponse,
    CompanyProfilePayload,
    CompanyMemberItem,
    CompanyRequestCreate,
    CompanyRequestsResponse,
    CompanyMatchItem,
    CompanyActionResponse,
)
from app.services.company_service import (
    get_company_status,
    set_company_profile,
    deactivate_company_profile,
    list_company_members,
    create_company_request,
    respond_to_company_request,
    cancel_company_request,
    list_requests,
    list_matches,
)

router = APIRouter(prefix="/events/{event_id}/company", tags=["Event Company Discovery"])


@router.get("/status", response_model=CompanyStatusResponse)
async def get_status_endpoint(
    event_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns aggregate company search status for the event.
    Works for both unauthenticated visitors (returns count only) and authenticated users.
    """
    return await get_company_status(session, event_id, user.id if user else None)


@router.post("/profile", response_model=CompanyStatusResponse)
async def update_profile_endpoint(
    event_id: str,
    payload: CompanyProfilePayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Opt-in or update companion discovery profile for this event.
    Requires that the user is participating (interested or attending).
    """
    _, status_resp = await set_company_profile(
        session,
        event_id=event_id,
        user=user,
        is_active=payload.is_active,
        note=payload.note
    )
    return status_resp


@router.delete("/profile", response_model=CompanyStatusResponse)
async def opt_out_endpoint(
    event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Opt-out: disables company profile visibility for this event without deleting match history.
    """
    return await deactivate_company_profile(session, event_id, user.id)


@router.get("/members", response_model=List[CompanyMemberItem])
async def get_members_endpoint(
    event_id: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists active company seekers for this event, excluding current user.
    Strict privacy: usernames, telegram IDs, and private data are NOT returned.
    """
    return await list_company_members(
        session,
        event_id=event_id,
        current_user_id=user.id,
        limit=limit,
        offset=offset
    )


@router.post("/requests", response_model=CompanyActionResponse)
async def send_request_endpoint(
    event_id: str,
    payload: CompanyRequestCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Sends a companion request to another participant.
    Cross-request auto-accept: if target previously sent a request, automatically creates Match.
    """
    req, match_created, match = await create_company_request(
        session,
        event_id=event_id,
        sender=user,
        target_user_id=payload.target_user_id
    )

    match_item = None
    if match:
        matches = await list_matches(session, event_id, user.id)
        for m in matches:
            if m.match_id == match.id:
                match_item = m
                break

    msg = "Взаимное совпадение найдено! Вы нашли компанию 🎉" if match_created else "Запрос отправлен"
    return CompanyActionResponse(
        ok=True,
        message=msg,
        match_created=match_created,
        match=match_item
    )


@router.get("/requests", response_model=CompanyRequestsResponse)
async def get_requests_endpoint(
    event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns incoming and outgoing requests for the current user and event.
    """
    return await list_requests(session, event_id, user.id)


@router.post("/requests/{request_id}/accept", response_model=CompanyActionResponse)
async def accept_request_endpoint(
    event_id: str,
    request_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Accepts an incoming companion request and creates a mutual Match.
    Only the receiver can accept.
    """
    req, match = await respond_to_company_request(
        session,
        event_id=event_id,
        request_id=request_id,
        current_user=user,
        action="accept"
    )

    match_item = None
    if match:
        matches = await list_matches(session, event_id, user.id)
        for m in matches:
            if m.match_id == match.id:
                match_item = m
                break

    return CompanyActionResponse(
        ok=True,
        message="Вы нашли компанию 🎉",
        match_created=True,
        match=match_item
    )


@router.post("/requests/{request_id}/decline", response_model=CompanyActionResponse)
async def decline_request_endpoint(
    event_id: str,
    request_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Declines an incoming companion request.
    """
    await respond_to_company_request(
        session,
        event_id=event_id,
        request_id=request_id,
        current_user=user,
        action="decline"
    )
    return CompanyActionResponse(
        ok=True,
        message="Запрос отклонен",
        match_created=False
    )


@router.delete("/requests/{request_id}", response_model=CompanyActionResponse)
async def cancel_request_endpoint(
    event_id: str,
    request_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Cancels an outgoing companion request before it is answered.
    """
    await cancel_company_request(
        session,
        event_id=event_id,
        request_id=request_id,
        current_user_id=user.id
    )
    return CompanyActionResponse(
        ok=True,
        message="Запрос отозван",
        match_created=False
    )


@router.get("/matches", response_model=List[CompanyMatchItem])
async def get_matches_endpoint(
    event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns confirmed mutual matches for the current user and event.
    Telegram @username is revealed ONLY here.
    """
    return await list_matches(session, event_id, user.id)
