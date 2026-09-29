import logging
from typing import List, Optional
import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.city import City

logger = logging.getLogger("ivently.locations")

router = APIRouter(prefix="/locations", tags=["Locations"])


class LocationSuggestion(BaseModel):
    title: str
    address: str
    city: Optional[str] = None
    latitude: float
    longitude: float
    display_name: str


def format_osm_item(
    item: dict,
    default_city_name: str,
    fallback_lat: float,
    fallback_lon: float
) -> LocationSuggestion:
    raw_display = item.get("display_name", "")
    addr = item.get("address", {})
    name = (item.get("name") or "").strip()
    road = (
        addr.get("road")
        or addr.get("pedestrian")
        or addr.get("street")
        or addr.get("avenue")
        or ""
    ).strip()
    house = (addr.get("house_number") or "").strip()
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or addr.get("suburb")
        or default_city_name
        or ""
    ).strip()

    # Determine clear, human title (venue / place name or street + house)
    if name and name != road:
        title = name
    elif road and house:
        title = f"{road}, {house}"
    elif road:
        title = road
    elif name:
        title = name
    else:
        title = raw_display.split(",")[0].strip()

    # Build clean human-readable address: street + house + city
    address_parts = []
    if road:
        street_str = f"{road}, {house}" if house else road
        address_parts.append(street_str)
    elif name and title != name:
        address_parts.append(name)

    if city and city not in address_parts:
        address_parts.append(city)

    if address_parts:
        clean_address = ", ".join(address_parts)
    else:
        clean_parts = [p.strip() for p in raw_display.split(",") if not p.strip().isdigit()][:3]
        clean_address = ", ".join(clean_parts) if clean_parts else raw_display

    try:
        lat = float(item.get("lat", fallback_lat))
        lon = float(item.get("lon", fallback_lon))
    except (ValueError, TypeError):
        lat, lon = fallback_lat, fallback_lon

    display = f"{title} ({clean_address})" if title != clean_address else clean_address

    return LocationSuggestion(
        title=title,
        address=clean_address,
        city=city or None,
        latitude=lat,
        longitude=lon,
        display_name=display,
    )


@router.get("/suggest", response_model=List[LocationSuggestion])
async def suggest_locations(
    q: str = Query(..., min_length=2, description="Address or venue search query"),
    city_id: Optional[str] = Query(None, description="City ID for contextual biasing"),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns human-friendly address suggestions with coordinates for venue search.
    Queries OpenStreetMap Nominatim with Russian language biasing,
    parses address components cleanly (stripping technical administrative noise),
    and falls back gracefully if Nominatim is unreachable.
    """
    clean_query = q.strip().rstrip(".,; ")
    city_name = ""
    city_lat = 42.9849  # Default to Makhachkala
    city_lon = 47.5047

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
        async with httpx.AsyncClient(timeout=4.0) as client:
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
                    "User-Agent": "Ivently-App/1.0 (https://t.me/Ivently_bot)",
                    "Accept-Language": "ru",
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    sugg = format_osm_item(item, city_name, city_lat, city_lon)
                    suggestions.append(sugg)
    except Exception as e:
        logger.warning(f"Nominatim lookup failed or timed out ({e}), using resilient local fallback")

    # 2. Resilient fallback if no external suggestions were obtained
    if not suggestions:
        fallback_display = f"{clean_query}, {city_name}" if city_name else clean_query
        suggestions.append(
            LocationSuggestion(
                title=clean_query,
                address=fallback_display,
                city=city_name or None,
                latitude=city_lat,
                longitude=city_lon,
                display_name=fallback_display,
            )
        )

    return suggestions
