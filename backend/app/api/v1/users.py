from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.schemas.event import EventSummary
from app.api.deps import get_current_user_optional, get_current_user
from app.services.event_service import get_user_personal_events

router = APIRouter(prefix="/users", tags=["Users"])


class UserProfileResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    default_city_id: Optional[str] = None
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)


@router.get("/me", response_model=Optional[UserProfileResponse])
async def get_current_user_profile(
    user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Returns authenticated user's profile and administrative status.
    Returns null if no Telegram authentication is provided.
    """
    if not user:
        return None

    is_admin = settings.is_admin(user.telegram_id)
    return UserProfileResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        avatar_url=user.avatar_url,
        default_city_id=user.default_city_id,
        is_admin=is_admin
    )


@router.get("/me/subscriptions")
async def get_my_subscriptions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns list of all organizations the authenticated user is subscribed to.
    """
    from app.services.organization_service import list_user_subscriptions
    return await list_user_subscriptions(session, user.id)


@router.get("/me/events", response_model=List[EventSummary])
async def get_my_personal_events(
    type: str = Query("attending", pattern="^(attending|interested)$", description="Filter personal events: 'attending' (Я иду) or 'interested' (Хочу пойти)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns personal events for the authenticated user:
    - 'attending': events user has RSVP'd to ('Я иду')
    - 'interested': events user has marked with interest ('Хочу пойти')
    """
    return await get_user_personal_events(
        session,
        user_id=user.id,
        event_type=type,
        limit=limit,
        offset=offset
    )

