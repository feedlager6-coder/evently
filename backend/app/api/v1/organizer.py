from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationStatus
from app.schemas.event import EventSummary
from app.schemas.audience import OrganizerAudienceResponse
from app.schemas.insights import OrganizerInsightsResponse
from app.schemas.broadcast import (
    BroadcastPreviewRequest,
    BroadcastPreviewResponse,
    BroadcastCreateRequest,
    BroadcastItem,
    BroadcastDetail,
)
from app.schemas.entitlement import (
    OrganizerEntitlementsResponse,
    CapabilityInfo,
    EntitlementLimits,
)
from app.api.deps import get_current_user
from app.services.event_service import get_organizer_events
from app.services.audience_service import get_organizer_audience
from app.services.insights_service import get_organizer_insights
from app.services.entitlement_service import EntitlementService, CAPABILITY_REGISTRY
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


@router.get("/insights", response_model=OrganizerInsightsResponse)
async def get_my_organizer_insights(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns unified organizer insights covering audience growth, event performance totals,
    broadcast attribution totals, and discovery source breakdown.
    """
    return await get_organizer_insights(session, organizer_user_id=user.id)


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


@router.get("/entitlements", response_model=OrganizerEntitlementsResponse)
async def get_my_entitlements(
    org_id: Optional[str] = Query(None, description="Optional organization ID to inspect entitlements for"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns verified capability entitlements and quota limits for the organizer.
    Strictly verifies organization ownership (403 for non-owner, 404 for deleted or non-existent).
    Returns only safe public metadata; never exposes internal secrets or private user data.
    """
    target_org_id = org_id
    org_name = None

    if target_org_id:
        # Check ownership and status
        org_stmt = select(Organization).where(Organization.id == target_org_id)
        org = (await session.execute(org_stmt)).scalar_one_or_none()
        if not org or org.status == OrganizationStatus.DELETED.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
        if org.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не являетесь владельцем этой организации")
        org_name = org.name
    else:
        # Lookup first active organization owned by this user
        user_orgs_stmt = (
            select(Organization)
            .where(
                Organization.owner_user_id == user.id,
                Organization.status != OrganizationStatus.DELETED.value
            )
            .order_by(Organization.created_at.asc())
        )
        first_org = (await session.execute(user_orgs_stmt)).scalars().first()
        if first_org:
            target_org_id = first_org.id
            org_name = first_org.name

    if not target_org_id:
        # User has no organizations yet: return default Free baseline
        return OrganizerEntitlementsResponse(
            organization_id=None,
            organization_name=None,
            plan="free",
            status="active",
            starts_at=None,
            expires_at=None,
            capabilities={
                key: CapabilityInfo(
                    key=key,
                    title=defn["title"],
                    description=defn["description"],
                    status=defn["plans"]["free"],
                    is_pro_feature=defn["is_pro_feature"],
                    limit=settings.FREE_BROADCASTS_PER_MONTH if key == "broadcasts_extended" else None,
                )
                for key, defn in CAPABILITY_REGISTRY.items()
            },
            limits=EntitlementLimits(
                broadcasts_per_month=settings.FREE_BROADCASTS_PER_MONTH,
                broadcasts_used_this_month=0,
                broadcasts_remaining=settings.FREE_BROADCASTS_PER_MONTH,
            ),
        )

    return await EntitlementService.get_entitlements(session, target_org_id, org_name=org_name)


