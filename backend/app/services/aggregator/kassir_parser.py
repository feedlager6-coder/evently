import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import httpx

from app.services.aggregator.models import AggregatedEvent
from app.services.aggregator.category_classifier import classify_event_category
from app.services.aggregator.city_mapping import (
    KASSIR_CITY_SUBDOMAINS,
    resolve_city_from_text,
)

logger = logging.getLogger("evently.aggregator.kassir")

KASSIR_RUBRICS = [
    "/bilety-na-koncert",
    "/bilety-v-teatr",
    "/detyam",
    "/bilety-na-sportivnye-meropriyatiya",
    "/shou",
]


class KassirParser:
    """
    Parser for Kassir.ru across supported cities using Nuxt 3 structured SSR data.
    """

    @classmethod
    async def fetch_city_events(
        cls,
        client: httpx.AsyncClient,
        city_id: str,
        max_events: int = 40,
    ) -> List[AggregatedEvent]:
        subdomain = KASSIR_CITY_SUBDOMAINS.get(city_id)
        if not subdomain:
            logger.debug("No Kassir subdomain mapping for city_id: %s", city_id)
            return []

        events: List[AggregatedEvent] = []
        seen_ids = set()

        for rubric in KASSIR_RUBRICS:
            if len(events) >= max_events:
                break

            url = f"https://{subdomain}.kassir.ru{rubric}"
            try:
                resp = await client.get(url, timeout=12.0)
                if resp.status_code != 200:
                    continue

                extracted = cls._parse_nuxt_data(resp.text, default_city_id=city_id, base_url=f"https://{subdomain}.kassir.ru")
                for ev in extracted:
                    if ev.external_id not in seen_ids and (ev.city_id == city_id or city_id in ["makhachkala", "derbent", "kaspiysk", "khasavyurt", "izberbash"]):
                        seen_ids.add(ev.external_id)
                        events.append(ev)
                        if len(events) >= max_events:
                            break
            except Exception as e:
                logger.warning("Error fetching Kassir %s %s: %s", subdomain, rubric, e)

        logger.info("Kassir parsed %d events for %s", len(events), city_id)
        return events

    @classmethod
    def _parse_nuxt_data(cls, html: str, default_city_id: str, base_url: str) -> List[AggregatedEvent]:
        m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            return []

        try:
            data = json.loads(m.group(1))
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        def resolve(val: Any) -> Any:
            if isinstance(val, int) and 0 <= val < len(data):
                return data[val]
            return val

        events: List[AggregatedEvent] = []

        for item in data:
            if not isinstance(item, dict):
                continue

            # Identify event card object in Nuxt data
            if "title" in item and ("beginsAt" in item or "posterImage" in item or "url" in item or "dateRange" in item):
                try:
                    title_val = resolve(item.get("title"))
                    if not title_val or not isinstance(title_val, str) or len(title_val.strip()) < 2:
                        continue

                    title = title_val.strip()
                    desc_val = resolve(item.get("description")) or ""
                    description = re.sub(r'<[^>]+>', ' ', str(desc_val)).strip() if desc_val else ""

                    # Venue & Address
                    venue_val = resolve(item.get("venueName")) or resolve(item.get("venue"))
                    venue_name = "Площадка мероприятия"
                    address = "Центр города"

                    if isinstance(venue_val, dict):
                        venue_name = str(resolve(venue_val.get("name")) or venue_name).strip()
                        addr_val = resolve(venue_val.get("address"))
                        if isinstance(addr_val, dict):
                            address = str(resolve(addr_val.get("addressString")) or address).strip()
                        elif isinstance(addr_val, str):
                            address = addr_val.strip()
                    elif isinstance(venue_val, str) and venue_val:
                        venue_name = venue_val.strip()

                    # City resolution (especially important for Dagestan multi-city subdomain)
                    target_city_id = resolve_city_from_text(
                        f"{venue_name} {address} {str(resolve(item.get('cityName')) or '')}",
                        default_city_id=default_city_id
                    ) or default_city_id

                    # Date / Start time
                    begins_at_val = resolve(item.get("beginsAt"))
                    start_at: Optional[datetime] = None

                    if begins_at_val and isinstance(begins_at_val, str):
                        try:
                            # ISO 8601 with tz or without
                            clean_dt = begins_at_val.replace('Z', '+00:00')
                            start_at = datetime.fromisoformat(clean_dt)
                            if start_at.tzinfo is None:
                                start_at = start_at.replace(tzinfo=timezone.utc)
                            else:
                                start_at = start_at.astimezone(timezone.utc)
                        except Exception:
                            pass

                    # Skip events in the past or without date
                    now_utc = datetime.now(timezone.utc)
                    if not start_at or start_at < now_utc:
                        continue

                    # URL / ticket link
                    url_val = resolve(item.get("url")) or resolve(item.get("canonicalLink")) or resolve(item.get("urlSlug"))
                    if not url_val or not isinstance(url_val, str):
                        continue

                    source_url = url_val.strip()
                    if not source_url.startswith("http"):
                        source_url = f"{base_url.rstrip('/')}/{source_url.lstrip('/')}"

                    # ID
                    ext_id = str(resolve(item.get("id")) or resolve(item.get("backofficeId")) or hash(source_url))

                    # Poster Image
                    poster_val = resolve(item.get("posterImage")) or resolve(item.get("horizontalImage"))
                    cover_image_url = None
                    if poster_val and isinstance(poster_val, str) and poster_val.startswith("http"):
                        cover_image_url = poster_val.strip()

                    # Price
                    price_min = None
                    price_max = None
                    price_range = resolve(item.get("priceRange"))
                    if isinstance(price_range, dict):
                        p_min = resolve(price_range.get("min"))
                        p_max = resolve(price_range.get("max"))
                        if isinstance(p_min, (int, float)):
                            price_min = float(p_min)
                        if isinstance(p_max, (int, float)):
                            price_max = float(p_max)
                    elif isinstance(price_range, (int, float)):
                        price_min = float(price_range)

                    # Age restriction
                    age_val = resolve(item.get("ageGroup")) or resolve(item.get("age"))
                    age_restriction = str(age_val).strip() if age_val else None

                    # Category
                    category_id = classify_event_category(
                        title=title,
                        description=description,
                        age_restriction=age_restriction,
                        venue_name=venue_name,
                    )

                    events.append(AggregatedEvent(
                        source_name="kassir",
                        external_id=f"kassir_{ext_id}",
                        source_url=source_url,
                        title=title,
                        description=description or f"Мероприятие «{title}» в городе {target_city_id.capitalize()}.",
                        start_at=start_at,
                        city_id=target_city_id,
                        venue_name=venue_name,
                        address=address,
                        price_min=price_min,
                        price_max=price_max,
                        price_currency="RUB",
                        cover_image_url=cover_image_url,
                        age_restriction=age_restriction,
                        category_id=category_id,
                    ))
                except Exception as parse_err:
                    logger.debug("Error parsing Kassir event item: %s", parse_err)

        return events
