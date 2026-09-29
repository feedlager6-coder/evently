from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.api.deps import get_current_user_optional
from app.schemas.discovery import UnifiedDiscoveryResponse
from app.services.discovery_service import discovery_service

router = APIRouter(prefix="/discovery", tags=["Discovery"])


@router.get("/search", response_model=UnifiedDiscoveryResponse)
async def search_discovery(
    q: str = Query(..., min_length=1, max_length=100, description="Search term for events, organizations, and places"),
    city_id: Optional[str] = Query(None, description="Optional city ID filter, e.g. 'makhachkala'"),
    category_id: Optional[str] = Query(None, description="Optional category filter"),
    limit: int = Query(15, ge=1, le=50, description="Maximum items per section"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db)
):
    """
    Unified multi-entity discovery endpoint.
    Searches published events, active organizations, and physical venues within the user's city context.
    Returns consolidated results in a single response to avoid multiple round-trip requests.
    """
    user_id = current_user.id if current_user else None
    return await discovery_service.unified_search(
        session=session,
        query=q,
        city_id=city_id,
        category_id=category_id,
        current_user_id=user_id,
        limit=limit
    )
