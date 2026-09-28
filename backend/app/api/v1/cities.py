from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.city import City
from app.models.user import User
from app.schemas.city import CityResponse
from app.api.deps import get_current_user_optional, get_current_user

router = APIRouter(prefix="/cities", tags=["Cities"])


@router.get("", response_model=List[CityResponse])
async def get_cities(
    session: AsyncSession = Depends(get_db)
):
    """Returns list of active supported cities."""
    result = await session.execute(
        select(City).where(City.is_active == True).order_by(City.name.asc())
    )
    return result.scalars().all()


@router.post("/default", response_model=CityResponse)
async def set_default_city(
    city_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Persists user's selected default city."""
    res = await session.execute(select(City).where(City.id == city_id, City.is_active == True))
    city = res.scalar_one_or_none()
    if not city:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active city '{city_id}' not found"
        )

    user.default_city_id = city.id
    await session.commit()
    await session.refresh(user)
    return city
