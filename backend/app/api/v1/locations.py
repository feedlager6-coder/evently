import logging
from typing import List, Optional
import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.city import City

logger = logging.getLogger("evently.locations")

router = APIRouter(prefix="/locations", tags=["Locations"])


class LocationSuggestion(BaseModel):
    display_name: str
    address: str
    latitude: float
    longitude: float


@router.get("/suggest", response_model=List[LocationSuggestion])
async def suggest_locations(
    q: str = Query(..., min_length=2, description="Address or venue search query"),
    city_id: Optional[str] = Query(None, description="City ID for contextual biasing"),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns address suggestions with geographic coordinates for venue search.
    Queries OpenStreetMap Nominatim with Russia / city biasing,
    with an automatic resilient local fallback if Nominatim is unreachable.
    """
    clean_query = q.strip()
    city_name = ""
    city_lat = 55.7558
    city_lon = 37.6173

    if city_id:
        try:
            c_res = await session.execute(select(City).where(City.id == city_id))
            city_obj = c_res.scalar_one_or_none()
            if city_obj:
                city_name = city_obj.name
                if city_obj.latitude and city_obj.longitude:
                    city_lat = city_obj.latitude
                    city_lon = city_obj.longitude
        except Exception as e:
            logger.warning(f"Error querying city in suggest_locations: {e}")

    # Build search query for OSM Nominatim
    search_q = clean_query
    if city_name and city_name.lower() not in clean_query.lower():
        search_q = f"{clean_query}, {city_name}"

    suggestions: List[LocationSuggestion] = []

    # 1. Attempt OpenStreetMap Nominatim lookup
    try:
        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": search_q,
                    "format": "jsonv2",
                    "addressdetails": "1",
                    "limit": "5",
                    "countrycodes": "ru",
                },
                headers={
                    "User-Agent": "Evently-App/1.0 (https://t.me/Ivently_bot)",
                    "Accept-Language": "ru",
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    display = item.get("display_name", "")
                    # Extract concise address
                    addr_parts = display.split(", ")
                    short_addr = ", ".join(addr_parts[:3]) if len(addr_parts) >= 3 else display
                    lat = float(item.get("lat", city_lat))
                    lon = float(item.get("lon", city_lon))
                    suggestions.append(
                        LocationSuggestion(
                            display_name=display,
                            address=short_addr,
                            latitude=lat,
                            longitude=lon,
                        )
                    )
    except Exception as e:
        logger.warning(f"Nominatim lookup failed or timed out ({e}), using resilient local fallback")

    # 2. Resilient fallback if no external suggestions were obtained
    if not suggestions:
        fallback_display = f"{clean_query}, {city_name}" if city_name else clean_query
        suggestions.append(
            LocationSuggestion(
                display_name=fallback_display,
                address=fallback_display,
                latitude=city_lat,
                longitude=city_lon,
            )
        )

    return suggestions
