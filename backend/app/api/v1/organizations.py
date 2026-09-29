from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationSummary,
    OrganizationResponse
)
from app.schemas.subscription import SubscriptionStatusResponse
from app.schemas.event import EventSummary
from app.api.deps import get_current_user, get_current_user_optional
from app.services.organization_service import (
    create_organization as create_org_service,
    get_organization_by_id_or_slug,
    update_organization as update_org_service,
    list_user_organizations,
    list_organization_events,
    subscribe_organization,
    unsubscribe_organization
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Creates a new organization owned by the authenticated Telegram user.
    """
    return await create_org_service(session, payload, owner_user_id=user.id)


@router.get("/me", response_model=List[OrganizationSummary])
async def get_my_organizations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists all organizations owned by the current user.
    """
    return await list_user_organizations(session, user.id)


@router.get("/{id_or_slug}", response_model=OrganizationResponse)
async def get_organization(
    id_or_slug: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db)
):
    """
    Public organization profile view by ID or slug.
    Returns public stats (followers_count) and personal is_subscribed flag if authenticated.
    """
    user_id = current_user.id if current_user else None
    return await get_organization_by_id_or_slug(session, id_or_slug, current_user_id=user_id)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    payload: OrganizationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Updates an organization profile.
    Strictly verifies ownership: 403 Forbidden if requester is not the owner.
    """
    return await update_org_service(session, org_id, payload, current_user_id=user.id)


@router.get("/{org_id}/events", response_model=List[EventSummary])
async def get_organization_events(
    org_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists published events for the organization.
    If viewed by the owner, also includes their pending events.
    """
    user_id = current_user.id if current_user else None
    return await list_organization_events(session, org_id, current_user_id=user_id)


@router.post("/{org_id}/subscribe", response_model=SubscriptionStatusResponse)
async def subscribe(
    org_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Subscribes the current user to the organization.
    Idempotent: repeating does not create duplicate records.
    """
    return await subscribe_organization(session, org_id, user.id)


@router.delete("/{org_id}/subscribe", response_model=SubscriptionStatusResponse)
async def unsubscribe(
    org_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Unsubscribes the current user from the organization.
    Idempotent: safe to call even if not subscribed.
    """
    return await unsubscribe_organization(session, org_id, user.id)
