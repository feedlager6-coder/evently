from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.event import EventSummary
from app.api.deps import get_current_user
from app.services.event_service import get_organizer_events

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
