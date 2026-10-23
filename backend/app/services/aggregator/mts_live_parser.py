import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set
import httpx

from app.services.aggregator.models import AggregatedEvent
from app.services.aggregator.category_classifier import classify_event_category
from app.services.aggregator.city_mapping import (
    MTS_CITY_SLUGS,
    resolve_city_from_text,
    validate_event_city,
)

logger = logging.getLogger("evently.aggregator.mts_live")

MTS_COLLECTIONS = [
    "ribbon",
    "concerts",
    "theatre",
    "standup",
    "kids",
    "show",
]


class MtsLiveParser:
    """
    Parser for MTS Live (live.mts.ru) using Next.js App Router streaming RSC payloads.
    """

    @classmethod
    async def fetch_city_events(
        cls,
        client: httpx.AsyncClient,
        city_id: str,
        max_events: int = 80,
    ) -> List[AggregatedEvent]:
        city_slug = MTS_CITY_SLUGS.get(city_id)
        if not city_slug:
            logger.debug("No MTS Live slug mapping for city_id: %s", city_id)
            return []

        events: List[AggregatedEvent] = []
        seen_ids: Set[str] = set()

        # 1. Fetch main city page (contains top featured events and bento sliders)
        try:
            main_url = f"https://live.mts.ru/{city_slug}"
            r = await client.get(main_url, timeout=12.0)
            if r.status_code == 200:
                extracted = cls._parse_rsc_payload(r.text, default_city_id=city_id)
                for ev in extracted:
                    if ev.external_id not in seen_ids:
                        seen_ids.add(ev.external_id)
                        events.append(ev)
        except Exception as e:
            logger.warning("Error fetching MTS Live main page for %s: %s", city_slug, e)

        # 2. Fetch category collections
        for col in MTS_COLLECTIONS:
            if len(events) >= max_events:
                break
            try:
                col_url = f"https://live.mts.ru/{city_slug}/collections/{col}"
                r = await client.get(col_url, timeout=12.0)
                if r.status_code == 200:
                    extracted = cls._parse_rsc_payload(r.text, default_city_id=city_id, default_rubric=col)
                    for ev in extracted:
                        if ev.external_id not in seen_ids:
                            seen_ids.add(ev.external_id)
                            events.append(ev)
                            if len(events) >= max_events:
                                break
            except Exception as e:
                logger.warning("Error fetching MTS Live collection %s for %s: %s", col, city_slug, e)

        logger.info("MTS Live parsed %d events for %s", len(events), city_id)
        return events

    @classmethod
    def _parse_rsc_payload(
        cls,
        html: str,
        default_city_id: str,
        default_rubric: Optional[str] = None,
    ) -> List[AggregatedEvent]:
        pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*"(.*?)"\s*\]\)', html, re.DOTALL)
        if not pushes:
            # Fallback pattern without push wrapper if raw JSON
            pushes = re.findall(r'(\{"announcementCollection":.*?\]\})', html, re.DOTALL)
        if not pushes:
            return []

        events: List[AggregatedEvent] = []
        now_utc = datetime.now(timezone.utc)

        for p in pushes:
            # Unescape JSON inside push chunk
            unescaped = (
                p.replace('\\"', '"')
                .replace('\\n', '\n')
                .replace('\\/', '/')
                .replace('\\u0026', '&')
                .replace('\\u003c', '<')
                .replace('\\u003e', '>')
            )

            # Check if this push contains event items
            if '"announcementCollection"' not in unescaped and '"eventMinPrice"' not in unescaped:
                continue

            # Extract all JSON arrays following '"items": [' with bracket matching
            items_arrays = []
            for m in re.finditer(r'"items":\s*\[', unescaped):
                start_idx = m.end() - 1
                depth = 0
                end_idx = -1
                for i in range(start_idx, len(unescaped)):
                    if unescaped[i] == '[':
                        depth += 1
                    elif unescaped[i] == ']':
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break
                if end_idx != -1:
                    try:
                        items_arr = json.loads(unescaped[start_idx:end_idx])
                        if isinstance(items_arr, list):
                            items_arrays.append(items_arr)
                    except Exception:
                        pass

            for items in items_arrays:
                try:
                    for it in items:
                        if not isinstance(it, dict) or not it.get("title"):
                            continue

                        ext_id = str(it.get("id") or it.get("alias") or "")
                        title = str(it.get("title", "")).strip()
                        if not title or len(title) < 2:
                            continue

                        # Date
                        dt_str = it.get("eventClosestDateTime")
                        start_at = None
                        if dt_str and isinstance(dt_str, str):
                            try:
                                clean_dt = dt_str.replace('Z', '+00:00')
                                start_at = datetime.fromisoformat(clean_dt)
                                if start_at.tzinfo is None:
                                    start_at = start_at.replace(tzinfo=timezone.utc)
                                else:
                                    start_at = start_at.astimezone(timezone.utc)
                            except Exception:
                                pass

                        if not start_at or start_at < now_utc:
                            continue

                        # Venue
                        venue_data = it.get("venue") or {}
                        venue_name = "Площадка мероприятия"
                        if isinstance(venue_data, dict) and venue_data.get("title"):
                            venue_name = str(venue_data["title"]).strip()
                        elif isinstance(venue_data, str) and venue_data:
                            venue_name = venue_data.strip()

                        address = f"г. {default_city_id.capitalize()}, {venue_name}"

                        # Price
                        price_min = None
                        if it.get("eventMinPrice") is not None:
                            try:
                                price_min = float(it["eventMinPrice"])
                            except Exception:
                                pass

                        # URL
                        raw_url = it.get("url") or ""
                        source_url = raw_url.strip()
                        if source_url and not source_url.startswith("http"):
                            source_url = f"https://live.mts.ru{source_url}"

                        if not source_url:
                            continue

                        # Image
                        image_url = it.get("imageUrl")
                        cover_image_url = None
                        if image_url and isinstance(image_url, str) and image_url.startswith("http"):
                            cover_image_url = image_url.strip()

                        # Description
                        raw_desc = it.get("description") or it.get("annotation") or it.get("subtitle") or it.get("lead") or ""
                        clean_desc = re.sub(r'<[^>]+>', ' ', str(raw_desc)).strip()
                        clean_desc = html.unescape(clean_desc)
                        if clean_desc and len(clean_desc) > 10:
                            description = clean_desc
                        else:
                            genre_str = f" ({raw_rubric})" if raw_rubric and raw_rubric not in ["ribbon", "announcements"] else ""
                            description = f"Событие «{title}»{genre_str}. Площадка: {venue_name} ({address}). Билеты доступны онлайн на МТС Live."

                        # Category
                        raw_rubric = default_rubric
                        for field in ["genre", "rubric", "category", "alias"]:
                            val = it.get(field)
                            if val and isinstance(val, str):
                                raw_rubric = val
                                break

                        category_id = classify_event_category(
                            title=title,
                            description=description,
                            raw_rubric=raw_rubric,
                            venue_name=venue_name,
                            source_url=source_url,
                        )

                        # Strict Anti-Geo-Spoofing check
                        if not validate_event_city(
                            source_name="mts_live",
                            source_url=source_url,
                            title=title,
                            venue_name=venue_name,
                            address=address,
                            target_city_id=default_city_id,
                        ):
                            logger.debug(
                                "MTS Live geo mismatch rejected: %s | URL: %s | Venue: %s for city %s",
                                title, source_url, venue_name, default_city_id
                            )
                            continue

                        events.append(AggregatedEvent(
                            source_name="mts_live",
                            external_id=f"mts_{ext_id}",
                            source_url=source_url,
                            title=title,
                            description=description,
                            start_at=start_at,
                            city_id=default_city_id,
                            venue_name=venue_name,
                            address=address,
                            price_min=price_min,
                            price_max=None,
                            price_currency="RUB",
                            cover_image_url=cover_image_url,
                            age_restriction=None,
                            category_id=category_id,
                        ))
                except Exception as json_err:
                    logger.debug("Error parsing MTS Live items array: %s", json_err)

        return events
