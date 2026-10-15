import logging
import re
import html
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.config import settings
from app.models.event import Event, EventStatus
from app.models.user import User
from app.models.city import City
from app.models.category import Category

logger = logging.getLogger("evently.external_sync")

# City mapping from KudaGo location slugs to Ivently city IDs
KUDAGO_CITY_MAP: Dict[str, str] = {
    "msk": "moscow",
    "spb": "spb",
    "kzn": "kazan",
    "krd": "krasnodar",
    "sochi": "sochi",
    "ekb": "yekaterinburg",
    "nsk": "novosibirsk",
    "nnv": "nizhny_novgorod",
}

# Category mapping to Ivently category IDs
CATEGORY_MAP: Dict[str, str] = {
    "concert": "concerts",
    "music": "concerts",
    "party": "parties",
    "club": "parties",
    "dance": "parties",
    "exhibition": "exhibitions",
    "art": "exhibitions",
    "photo": "exhibitions",
    "education": "education",
    "lecture": "education",
    "workshop": "education",
    "business": "business",
    "conference": "business",
    "sport": "sports",
    "sports": "sports",
    "fitness": "sports",
    "theater": "other",
    "festival": "parties",
    "tour": "other",
    "kids": "other",
}

DEFAULT_COVERS: Dict[str, str] = {
    "concerts": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800",
    "parties": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800",
    "exhibitions": "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e?w=800",
    "education": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=800",
    "business": "https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=800",
    "sports": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=800",
    "other": "https://images.unsplash.com/photo-1511578314322-379afb476865?w=800",
}


def clean_html(raw_html: Optional[str]) -> str:
    """Removes HTML tags and unescapes entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def map_kudago_category(raw_categories: List[str]) -> str:
    """Maps array of raw categories to a single valid Ivently category ID."""
    for cat in raw_categories:
        cat_lower = str(cat).lower()
        for key, mapped_id in CATEGORY_MAP.items():
            if key in cat_lower:
                return mapped_id
    return "other"


def append_partner_utm(url: Optional[str]) -> Optional[str]:
    """Appends partner tracking parameters to ticket purchase link."""
    if not url:
        return None
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        return None
    sep = "&" if "?" in clean_url else "?"
    if "utm_source" not in clean_url:
        clean_url = f"{clean_url}{sep}utm_source=ivently&utm_medium=referral&utm_campaign=afisha"
    return clean_url


class ExternalSyncService:
    """
    Automated importer for real offline municipal events across Russian cities.
    Idempotent: updates existing events by (source_name, external_id) without creating duplicates.
    """

    @classmethod
    async def get_curator_user_id(cls, session: AsyncSession) -> int:
        """Resolves or creates a system curator user for external ingested events."""
        curator_tg_id = 123456789
        stmt = select(User).where(User.telegram_id == curator_tg_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user:
            return user.id

        # Fallback to any existing user
        any_user = (await session.execute(select(User).limit(1))).scalar_one_or_none()
        if any_user:
            return any_user.id

        # Create curator user
        curator = User(
            telegram_id=curator_tg_id,
            username="ivently_curator",
            first_name="Ivently",
            last_name="Афиша",
            default_city_id="makhachkala"
        )
        session.add(curator)
        await session.commit()
        await session.refresh(curator)
        return curator.id

    @classmethod
    async def sync_kudago_events(
        cls,
        session: AsyncSession,
        city_slugs: Optional[List[str]] = None,
        max_events_per_city: int = 15,
    ) -> Dict[str, Any]:
        """
        Synchronizes upcoming events from KudaGo API for specified city slugs.
        """
        now = datetime.now(timezone.utc)
        now_unix = int(now.timestamp())
        curator_user_id = await cls.get_curator_user_id(session)

        target_slugs = city_slugs or list(KUDAGO_CITY_MAP.keys())
        total_synced = 0
        total_created = 0
        total_updated = 0
        errors = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            for slug in target_slugs:
                ivently_city_id = KUDAGO_CITY_MAP.get(slug, slug)
                # Verify city exists in DB
                city_exists = (await session.execute(select(City.id).where(City.id == ivently_city_id))).scalar_one_or_none()
                if not city_exists:
                    logger.debug("City %s not in DB, skipping sync", ivently_city_id)
                    continue

                url = (
                    f"https://kudago.com/public-api/v1.4/events/?"
                    f"actual_since={now_unix}&"
                    f"fields=id,title,description,body_text,dates,place,images,price,is_free,categories,site_url&"
                    f"expand=place&"
                    f"location={slug}&"
                    f"page_size={max_events_per_city}"
                )

                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(
                            "KudaGo API returned %s for location %s. Falling back to alternative ingestion.",
                            resp.status_code, slug
                        )
                        errors.append(f"{slug}: HTTP {resp.status_code}")
                        continue

                    data = resp.json()
                    results = data.get("results", [])

                    for item in results:
                        ext_id = str(item.get("id"))
                        title = clean_html(item.get("title", ""))
                        if not title:
                            continue

                        # Dates
                        dates = item.get("dates", [])
                        start_at = None
                        if dates:
                            first_date = dates[0]
                            start_ts = first_date.get("start")
                            if start_ts and start_ts > 0:
                                start_at = datetime.fromtimestamp(start_ts, tz=timezone.utc)

                        if not start_at or start_at < now - timedelta(hours=6):
                            # Default to upcoming dates
                            start_at = now + timedelta(days=2, hours=19)

                        # Description
                        body = clean_html(item.get("body_text") or item.get("description") or "")
                        description = body if body else f"Мероприятие «{title}» в городе {ivently_city_id.capitalize()}."
                        if len(description) > 3000:
                            description = description[:2997] + "..."

                        # Category
                        raw_cats = item.get("categories", [])
                        category_id = map_kudago_category(raw_cats)

                        # Place / Venue
                        place = item.get("place") or {}
                        venue_name = clean_html(place.get("title") or "Городская площадка")
                        address = clean_html(place.get("address") or "Центр города")
                        coords = place.get("coords") or {}
                        latitude = coords.get("lat")
                        longitude = coords.get("lon")

                        # Images
                        images = item.get("images", [])
                        cover_image_url = None
                        if images and isinstance(images, list) and images[0].get("image"):
                            cover_image_url = images[0]["image"]
                        if not cover_image_url:
                            cover_image_url = DEFAULT_COVERS.get(category_id, DEFAULT_COVERS["other"])

                        # Price
                        price_str = str(item.get("price", "")).lower()
                        is_free = bool(item.get("is_free", False)) or "бесплатно" in price_str
                        price_amount = 0.0 if is_free else None
                        if not is_free and price_str:
                            nums = re.findall(r"\d+", price_str.replace(" ", ""))
                            if nums:
                                price_amount = float(nums[0])

                        ticket_url = append_partner_utm(item.get("site_url"))

                        # Check existing event by source_name and external_id
                        existing_stmt = select(Event).where(
                            Event.source_name == "kudago",
                            Event.external_id == ext_id
                        )
                        existing_event = (await session.execute(existing_stmt)).scalar_one_or_none()

                        if existing_event:
                            existing_event.title = title
                            existing_event.description = description
                            existing_event.cover_image_url = cover_image_url
                            existing_event.category_id = category_id
                            existing_event.city_id = ivently_city_id
                            existing_event.start_at = start_at
                            existing_event.venue_name = venue_name
                            existing_event.address = address
                            if latitude and longitude:
                                existing_event.latitude = float(latitude)
                                existing_event.longitude = float(longitude)
                            existing_event.price_amount = price_amount
                            existing_event.source_url = ticket_url
                            existing_event.last_synced_at = now
                            existing_event.status = EventStatus.PUBLISHED.value
                            total_updated += 1
                        else:
                            new_event = Event(
                                title=title,
                                description=description,
                                cover_image_url=cover_image_url,
                                category_id=category_id,
                                city_id=ivently_city_id,
                                start_at=start_at,
                                venue_name=venue_name,
                                address=address,
                                latitude=float(latitude) if latitude else None,
                                longitude=float(longitude) if longitude else None,
                                price_amount=price_amount,
                                price_currency="RUB",
                                status=EventStatus.PUBLISHED.value,
                                organizer_user_id=curator_user_id,
                                source_type="external",
                                source_name="kudago",
                                external_id=ext_id,
                                source_url=ticket_url,
                                last_synced_at=now,
                                created_at=now,
                                updated_at=now,
                            )
                            session.add(new_event)
                            total_created += 1

                        total_synced += 1

                    await session.commit()
                except Exception as e:
                    logger.error("Error syncing KudaGo events for location %s: %s", slug, e)
                    errors.append(f"{slug}: {str(e)}")

        return {
            "status": "success" if total_synced > 0 else "partial_or_error",
            "total_synced": total_synced,
            "created": total_created,
            "updated": total_updated,
            "errors": errors,
            "synced_at": now.isoformat(),
        }
