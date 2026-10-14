import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.database import get_db
from app.models.city import City
from app.models.user import User
from app.schemas.city import CityResponse
from app.api.deps import get_current_user_optional, get_current_user

router = APIRouter(prefix="/cities", tags=["Cities"])


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points on a sphere in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


_CITIES_CACHE: Optional[List[City]] = None
_CITIES_CACHE_TIME: float = 0.0


async def _get_cached_active_cities(session: AsyncSession) -> List[City]:
    global _CITIES_CACHE, _CITIES_CACHE_TIME
    import time
    now = time.time()
    if _CITIES_CACHE is not None and (now - _CITIES_CACHE_TIME) < 60:
        return _CITIES_CACHE

    stmt = select(City).where(City.is_active == True).order_by(City.name.asc())
    result = await session.execute(stmt)
    _CITIES_CACHE = list(result.scalars().all())
    _CITIES_CACHE_TIME = now
    return _CITIES_CACHE


@router.get("", response_model=List[CityResponse])
async def get_cities(
    response: Response,
    q: Optional[str] = Query(None, description="Search city by name"),
    limit: Optional[int] = Query(None, description="Limit result count", ge=1, le=2000),
    session: AsyncSession = Depends(get_db)
):
    """Returns list of active supported cities with search filtering and HTTP caching."""
    cities = await _get_cached_active_cities(session)

    if q and q.strip():
        term = q.strip().lower()
        filtered = [c for c in cities if term in c.name.lower() or term in c.id.lower()]
        if limit:
            filtered = filtered[:limit]
        response.headers["Cache-Control"] = "private, no-cache"
        return filtered

    if limit:
        cities = cities[:limit]

    # Cache catalog response for 24 hours to accelerate client warm startups
    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
    return cities


@router.get("/nearest", response_model=CityResponse)
async def get_nearest_city(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="User latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="User longitude"),
    session: AsyncSession = Depends(get_db)
):
    """
    Finds the nearest supported Russian city based on user's geographic coordinates.
    Uses in-memory cache to guarantee sub-millisecond response time.
    """
    cities = await _get_cached_active_cities(session)
    if not cities:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active cities found")

    nearest_city = None
    min_dist = float("inf")

    for city in cities:
        if city.latitude is not None and city.longitude is not None:
            dist = haversine_distance_km(latitude, longitude, city.latitude, city.longitude)
            if dist < min_dist:
                min_dist = dist
                nearest_city = city

    return nearest_city or cities[0]



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
