import asyncio
import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set, Dict, Any
import httpx

from app.services.aggregator.models import AggregatedEvent
from app.services.aggregator.category_classifier import classify_event_category
from app.services.aggregator.city_mapping import (
    KASSIR_CITY_SUBDOMAINS,
    resolve_city_from_text,
    validate_event_city,
)

logger = logging.getLogger("evently.aggregator.kassir")

KASSIR_RUBRICS = [
    "",                                      # Top upcoming on city subdomain
    "/bilety-na-koncert",                    # Concerts & Live Music
    "/bilety-v-teatr",                       # Theatre, Opera, Ballet
    "/standup",                              # Standup & Comedy
    "/ekskursii",                            # City & Cultural excursions
    "/bilety-v-muzei-i-galerei",             # Museums, Exhibitions, Galleries
    "/shou",                                 # Circus, Show, Musicals
    "/bilety-na-sportivnye-meropriyatiya",   # Sports & Matches
    "/detyam",                               # Children & Family events
]


class KassirParser:
    """
    Parser for Kassir.ru across supported cities using Nuxt 3 structured SSR data.
    Safely navigates subdomains, parses arrays, prices, venues, and direct ticketing links.
    """

    @classmethod
    async def fetch_city_events(
        cls,
        client: httpx.AsyncClient,
        city_id: str,
        max_events: int = 80,
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
                # Polite rate limiting to protect connection
                await asyncio.sleep(0.35)
                resp = await client.get(url, timeout=12.0)
                if resp.status_code == 429:
                    logger.warning("Kassir rate limited on %s (HTTP 429), backing off...", url)
                    await asyncio.sleep(2.0)
                    continue
                if resp.status_code != 200:
                    continue

                extracted = cls._parse_nuxt_data(
                    resp.text,
                    default_city_id=city_id,
                    base_url=f"https://{subdomain}.kassir.ru",
                    default_rubric=rubric.replace("/", "").replace("-", "_") if rubric else "featured",
                )
                for ev in extracted:
                    if ev.external_id not in seen_ids and ev.city_id == city_id:
                        seen_ids.add(ev.external_id)
                        events.append(ev)
                        if len(events) >= max_events:
                            break
            except Exception as e:
                logger.warning("Error fetching Kassir %s%s: %s", subdomain, rubric, e)

        logger.info("Kassir.ru parsed %d events for %s", len(events), city_id)
        return events

    @classmethod
    def _parse_nuxt_data(
        cls,
        html: str,
        default_city_id: str,
        base_url: str,
        default_rubric: Optional[str] = None,
    ) -> List[AggregatedEvent]:
        m = re.search(r"<script[^>]*id=[\"']__NUXT_DATA__[\"'][^>]*>(.*?)</script>", html, re.DOTALL)
        if not m:
            return []

        try:
            raw_data = json.loads(m.group(1))
        except Exception as e:
            logger.debug("Failed to parse __NUXT_DATA__ JSON: %s", e)
            return []

        if not isinstance(raw_data, list):
            return []

        def resolve(val: Any) -> Any:
            """Resolves Nuxt 3 indexed pointers in raw_data list."""
            if isinstance(val, int) and 0 <= val < len(raw_data):
                target = raw_data[val]
                if isinstance(target, (str, int, float, bool)) or target is None:
                    return target
                return target
            return val

        events: List[AggregatedEvent] = []
        now_utc = datetime.now(timezone.utc)

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            # Identify Event objects in Nuxt state
            if "title" in entry and ("beginsAt" in entry or "alias" in entry or "priceRange" in entry or "horizontalImage" in entry):
                item = entry
                try:
                    title_val = resolve(item.get("title"))
                    if not title_val or not isinstance(title_val, str) or len(title_val.strip()) < 2:
                        continue

                    title = title_val.strip()

                    # Date parsing
                    begins_at_val = resolve(item.get("beginsAt")) or resolve(item.get("date")) or resolve(item.get("dateStart"))
                    start_at = None
                    if begins_at_val and isinstance(begins_at_val, str):
                        try:
                            clean_dt = begins_at_val.replace('Z', '+00:00')
                            dt_obj = datetime.fromisoformat(clean_dt)
                            if dt_obj.tzinfo is None:
                                start_at = dt_obj.replace(tzinfo=timezone.utc)
                            else:
                                start_at = dt_obj.astimezone(timezone.utc)
                        except Exception:
                            pass

                    # Filter past events
                    if not start_at or start_at < now_utc:
                        continue

                    # Venue & Address
                    venue_obj = resolve(item.get("venue"))
                    venue_name = "Площадка мероприятия"
                    address = f"г. {default_city_id.capitalize()}"

                    if isinstance(venue_obj, dict):
                        v_title = resolve(venue_obj.get("title")) or resolve(venue_obj.get("name")) or resolve(item.get("venueName"))
                        v_addr = resolve(venue_obj.get("address"))
                        if isinstance(v_addr, dict):
                            v_addr = resolve(v_addr.get("addressString")) or resolve(v_addr.get("title"))
                        if v_title and isinstance(v_title, str):
                            venue_name = v_title.strip()
                        if v_addr and isinstance(v_addr, str):
                            address = v_addr.strip()
                    elif isinstance(venue_obj, str) and venue_obj.strip():
                        venue_name = venue_obj.strip()
                    elif item.get("venueName"):
                        v_name_direct = resolve(item.get("venueName"))
                        if v_name_direct and isinstance(v_name_direct, str):
                            venue_name = v_name_direct.strip()

                    if address == f"г. {default_city_id.capitalize()}":
                        address = f"г. {default_city_id.capitalize()}, {venue_name}"

                    # City resolution (especially for multi-city regional subdomains like dagestan)
                    target_city_id = resolve_city_from_text(f"{address} {venue_name} {title}", default_city_id=default_city_id)

                    # External ID and Source URL
                    alias_val = resolve(item.get("alias")) or resolve(item.get("id"))
                    ext_id = str(resolve(item.get("id")) or alias_val)
                    url_val = resolve(item.get("url")) or resolve(item.get("canonicalUrl"))

                    if url_val and isinstance(url_val, str):
                        source_url = url_val if url_val.startswith("http") else f"{base_url}{url_val}"
                    elif alias_val:
                        source_url = f"{base_url}/event/{alias_val}"
                    else:
                        continue

                    # Reject cross-promoted banners from foreign subdomains (e.g. msk.kassir.ru on dagestan.kassir.ru)
                    if source_url.startswith("http") and not source_url.startswith(base_url):
                        continue

                    # Rich Description Parsing (clean HTML and entities)
                    raw_desc = resolve(item.get("description")) or resolve(item.get("annotation")) or resolve(item.get("lead")) or ""
                    clean_desc = re.sub(r'<[^>]+>', ' ', str(raw_desc)).strip()
                    clean_desc = html.unescape(clean_desc)
                    clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
                    if clean_desc and len(clean_desc) > 10:
                        description = clean_desc
                    else:
                        description = f"Событие «{title}». Площадка: {venue_name} ({address}). Билеты доступны онлайн на Kassir.ru."

                    # Images
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

                    # Category resolution: infer from source_url path or default_rubric
                    inferred_rubric = default_rubric
                    s_url_low = source_url.lower()
                    if any(x in s_url_low for x in ["/koncert", "/bilety-na-koncert"]):
                        inferred_rubric = "concerts"
                    elif any(x in s_url_low for x in ["/teatr", "/bilety-v-teatr"]):
                        inferred_rubric = "theatre"
                    elif "/standup" in s_url_low:
                        inferred_rubric = "standup"
                    elif any(x in s_url_low for x in ["/muzej", "/muzei", "/vystavk", "/bilety-v-muzei"]):
                        inferred_rubric = "exhibitions"
                    elif any(x in s_url_low for x in ["/ekskurs", "/seminar"]):
                        inferred_rubric = "education"
                    elif "/shou" in s_url_low:
                        inferred_rubric = "show"
                    elif any(x in s_url_low for x in ["/sport", "/bilety-na-sportivnye"]):
                        inferred_rubric = "sports"
                    elif "/detyam" in s_url_low:
                        inferred_rubric = "kids"

                    category_id = classify_event_category(
                        title=title,
                        description=description,
                        raw_rubric=inferred_rubric,
                        age_restriction=age_restriction,
                        venue_name=venue_name,
                        source_url=source_url,
                    )

                    # Strict Anti-Geo-Spoofing check
                    if not validate_event_city(
                        source_name="kassir",
                        source_url=source_url,
                        title=title,
                        venue_name=venue_name,
                        address=address,
                        target_city_id=target_city_id,
                    ):
                        logger.debug(
                            "Kassir geo mismatch rejected: %s | URL: %s | Venue: %s for city %s",
                            title, source_url, venue_name, target_city_id
                        )
                        continue

                    events.append(AggregatedEvent(
                        source_name="kassir",
                        external_id=f"kassir_{ext_id}",
                        source_url=source_url,
                        title=title,
                        description=description,
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
                    logger.debug("Error parsing Kassir Nuxt item: %s", parse_err)

        return events
