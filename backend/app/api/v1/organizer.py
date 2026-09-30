from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.event import EventSummary
from app.schemas.audience import OrganizerAudienceResponse
from app.schemas.broadcast import (
    BroadcastPreviewRequest,
    BroadcastPreviewResponse,
    BroadcastCreateRequest,
    BroadcastItem,
    BroadcastDetail,
)
from app.api.deps import get_current_user
from app.services.event_service import get_organizer_events
from app.services.audience_service import get_organizer_audience
from app.services.broadcast_service import (
    preview_broadcast,
    create_broadcast,
    list_organizer_broadcasts,
    get_broadcast_detail,
)

router = APIRouter(prefix="/organizer", tags=["Organizer"])


@router.get("/events", response_model=List[EventSummary])
async def list_my_organized_events(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns all events created by the authenticated organizer across all moderation states:
    pending, published, rejected, and cancelled.
    """
    return await get_organizer_events(session, organizer_user_id=user.id)


@router.get("/audience", response_model=OrganizerAudienceResponse)
async def get_audience_overview(
    org_id: Optional[str] = Query(None, description="Optional organization ID to filter audience metrics"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns comprehensive, un-faked audience metrics for the authenticated organizer.
    Includes subscriber totals, 7d/30d growth, event interaction metrics, and deduplicated unique reach.
    """
    return await get_organizer_audience(session, organizer_user_id=user.id, target_org_id=org_id)


@router.post("/broadcasts/preview", response_model=BroadcastPreviewResponse)
async def preview_organizer_broadcast(
    req: BroadcastPreviewRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Calculates verified audience and renders message preview without sending.
    """
    return await preview_broadcast(
        session=session,
        organizer_user_id=user.id,
        organization_id=req.organization_id,
        target_type=getattr(req.target_type, 'value', req.target_type),
        broadcast_type=getattr(req.broadcast_type, 'value', req.broadcast_type),
        template_key=getattr(req.template_key, 'value', req.template_key),
        event_id=req.event_id,
        custom_text=req.custom_text,
    )


@router.post("/broadcasts", response_model=BroadcastDetail)
async def create_organizer_broadcast(
    req: BroadcastCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Creates and dispatches an organizer broadcast campaign.
    """
    return await create_broadcast(
        session=session,
        organizer_user_id=user.id,
        req=req,
    )


@router.get("/broadcasts", response_model=List[BroadcastItem])
async def get_my_broadcasts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists all broadcast campaigns for organizations owned by the organizer.
    """
    return await list_organizer_broadcasts(session, organizer_user_id=user.id)


@router.get("/broadcasts/{broadcast_id}", response_model=BroadcastDetail)
async def get_broadcast_by_id(
    broadcast_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns detailed delivery metrics and message preview for a specific broadcast.
    """
    return await get_broadcast_detail(session, organizer_user_id=user.id, broadcast_id=broadcast_id)

