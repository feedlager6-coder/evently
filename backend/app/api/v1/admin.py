from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.event import EventSummary, EventResponse
from app.schemas.moderation import RejectRequest
from app.api.deps import require_admin
from app.services.moderation_service import (
    get_admin_events,
    publish_event,
    reject_event,
    cancel_event
)
from app.services.event_service import get_event_details, EventNotFoundError

router = APIRouter(prefix="/admin", tags=["Admin Moderation"])


@router.get("/events", response_model=List[EventSummary])
async def list_moderation_queue(
    status: Optional[str] = Query(None, pattern="^(pending|published|rejected|cancelled|all)$"),
    status_filter: Optional[str] = Query(None, pattern="^(pending|published|rejected|cancelled|all)$"),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Admin moderation queue. Lists events filtered by status (default 'pending').
    Accepts both ?status= and ?status_filter= parameters for seamless frontend compatibility.
    Protected by admin RBAC check.
    """
    raw_status = status or status_filter or "pending"
    effective_status = None if raw_status == "all" else raw_status
    return await get_admin_events(session, status_filter=effective_status)


@router.post("/events/{event_id}/publish", response_model=EventResponse)
async def admin_publish_event(
    event_id: str,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Approves and publishes an event, making it immediately visible in public discovery.
    """
    try:
        await publish_event(session, event_id)
        return await get_event_details(session, event_id)
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/events/{event_id}/reject", response_model=EventResponse)
async def admin_reject_event(
    event_id: str,
    payload: Optional[RejectRequest] = None,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Rejects an event submission with an optional explanation.
    """
    reason = payload.reason if payload else None
    try:
        await reject_event(session, event_id, reason=reason)
        return await get_event_details(session, event_id)
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/events/{event_id}/cancel", response_model=EventResponse)
async def admin_cancel_event(
    event_id: str,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Cancels a previously published event, removing it from public discovery.
    """
    try:
        await cancel_event(session, event_id)
        return await get_event_details(session, event_id)
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
