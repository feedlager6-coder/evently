from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.api.deps import get_current_user_optional, get_current_user

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
