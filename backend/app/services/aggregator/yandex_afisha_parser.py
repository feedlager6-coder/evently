import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set, Dict, Any
import httpx

from app.services.aggregator.models import AggregatedEvent
from app.services.aggregator.category_classifier import classify_event_category
from app.services.aggregator.city_mapping import (
    YANDEX_CITY_SLUGS,
    resolve_city_from_text,
)

logger = logging.getLogger("evently.aggregator.yandex_afisha")

# Core rubrics available across Yandex.Afisha cities
YANDEX_RUBRICS = [
    "",           # Main city page with top featured / upcoming
    "concert",    # Concerts & Live Music
    "theatre",    # Theatre, Opera, Ballet
    "standup",    # Standup & Comedy
    "art",        # Exhibitions, Museums & Galleries
    "show",       # Shows, Musicals, Circus
    "kids",       # Children & Family
    "sport",      # Sports events & Matches
]


class YandexAfishaParser:
    """
    Parser for Yandex.Afisha (afisha.yandex.ru) using Apollo GraphQL normalized client cache.
    Extracts structured events, multi-session dates, high-res posters, and direct ticket links.
    Features robust error isolation on HTTP 403 / captcha challenges.
    """

    @classmethod
    async def fetch_city_events(
        cls,
        client: httpx.AsyncClient,
        city_id: str,
        max_events: int = 80,
    ) -> List[AggregatedEvent]:
        city_slug = YANDEX_CITY_SLUGS.get(city_id)
        if not city_slug:
            logger.debug("No Yandex.Afisha slug mapping for city_id: %s", city_id)
            return []

        events: List[AggregatedEvent] = []
        seen_ids: Set[str] = set()

        for rubric in YANDEX_RUBRICS:
            if len(events) >= max_events:
                break
            url = f"https://afisha.yandex.ru/{city_slug}/{rubric}" if rubric else f"https://afisha.yandex.ru/{city_slug}"
            try:
                resp = await client.get(url, timeout=12.0)
                if resp.status_code == 403:
                    logger.warning("Yandex.Afisha returned 403 for %s/%s (WAF/Anti-Bot active)", city_slug, rubric)
                    continue
                if resp.status_code != 200:
                    continue

                extracted = cls._parse_apollo_state(resp.text, default_city_id=city_id, default_rubric=rubric or "featured")
                for ev in extracted:
                    if ev.external_id not in seen_ids:
                        seen_ids.add(ev.external_id)
                        events.append(ev)
                        if len(events) >= max_events:
                            break
            except Exception as e:
                logger.warning("Error fetching Yandex.Afisha %s/%s: %s", city_slug, rubric, e)

        logger.info("Yandex.Afisha parsed %d events for %s", len(events), city_id)
        return events

    @classmethod
    def _parse_apollo_state(
        cls,
        html: str,
        default_city_id: str,
        default_rubric: Optional[str] = None,
    ) -> List[AggregatedEvent]:
        m = re.search(r"window\[[\x27\"]__APOLLO_STATE__[\x27\"]\]\s*=\s*(.*?);\s*</script>", html, re.DOTALL)
        if not m:
            return []

        raw = m.group(1)
        # Sanitize JavaScript Date and undefined for JSON parsing
        clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', raw)
        clean = re.sub(r"\bundefined\b", "null", clean)

        try:
            data: Dict[str, Any] = json.loads(clean)
        except Exception as e:
            logger.debug("Failed to parse Apollo JSON: %s", e)
            return []

        events: List[AggregatedEvent] = []
        now_utc = datetime.now(timezone.utc)

        # Lookup maps for Tickets, Places, and ScheduleInfo
        tickets_map: Dict[str, Any] = {}
        places_map: Dict[str, Any] = {}
        schedule_by_event_id: Dict[str, Any] = {}

        # 1. First pass: Index Tickets, Places, and direct/nested ActualEvent / Featured objects
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            tname = v.get("__typename")
            if tname == "Ticket":
                tickets_map[k] = v
            elif tname in ["Place", "PlacePreview"]:
                places_map[k] = v
            elif tname == "ActualEvent":
                ev_ref = v.get("event", {}).get("__ref") if isinstance(v.get("event"), dict) else None
                sched = v.get("scheduleInfo")
                if ev_ref and sched:
                    schedule_by_event_id[ev_ref] = sched
            elif tname == "Featured" and isinstance(v.get("object"), dict):
                obj = v["object"]
                ev_ref = obj.get("event", {}).get("__ref") if isinstance(obj.get("event"), dict) else None
                sched = obj.get("scheduleInfo")
                if ev_ref and sched:
                    schedule_by_event_id[ev_ref] = sched

        # 2. Check ROOT_QUERY lists for actualEventsById or rubric events
        rq = data.get("ROOT_QUERY", {})
        if isinstance(rq, dict):
            for pk, pv in rq.items():
                if isinstance(pv, list):
                    for item in pv:
                        if isinstance(item, dict) and item.get("__typename") == "ActualEvent":
                            ev_ref = item.get("event", {}).get("__ref") if isinstance(item.get("event"), dict) else None
                            sched = item.get("scheduleInfo")
                            if ev_ref and sched:
                                schedule_by_event_id[ev_ref] = sched

        # 3. Extract EventPreviews
        for k, v in data.items():
            if not isinstance(v, dict) or v.get("__typename") != "EventPreview":
                continue

            title = str(v.get("title") or "").strip()
            if not title or len(title) < 2:
                continue

            raw_url = str(v.get("url") or "").strip()
            if not raw_url:
                continue

            source_url = raw_url if raw_url.startswith("http") else f"https://afisha.yandex.ru{raw_url}"
            ext_id = str(v.get("id") or hash(source_url))

            # Schedule / Date / Venue
            start_at: Optional[datetime] = None
            venue_name = "Площадка мероприятия"
            price_min: Optional[float] = None
            price_max: Optional[float] = None

            sched = schedule_by_event_id.get(k) or schedule_by_event_id.get(f"Event:{ext_id}")

            if sched and isinstance(sched, dict):
                # A. Regularity singleShowtime e.g. "2026-11-06T18:30:00"
                reg = sched.get("regularity")
                showtime = None
                if isinstance(reg, dict) and reg.get("singleShowtime"):
                    showtime = reg.get("singleShowtime")
                elif sched.get("dates") and isinstance(sched["dates"], list):
                    # Filter dates in future
                    for d in sched["dates"]:
                        try:
                            d_parsed = datetime.fromisoformat(f"{d}T19:00:00+00:00")
                            if d_parsed >= now_utc:
                                showtime = f"{d}T19:00:00"
                                break
                        except Exception:
                            pass
                elif sched.get("dateStarted"):
                    showtime = f"{sched['dateStarted']}T19:00:00"

                if showtime:
                    try:
                        clean_dt = str(showtime).replace('Z', '+00:00')
                        dt_obj = datetime.fromisoformat(clean_dt)
                        if dt_obj.tzinfo is None:
                            start_at = dt_obj.replace(tzinfo=timezone.utc)
                        else:
                            start_at = dt_obj.astimezone(timezone.utc)
                    except Exception:
                        pass

                # Venue name from scheduleInfo
                if sched.get("placePreview"):
                    venue_name = str(sched["placePreview"]).strip()

                # Prices from scheduleInfo
                for pr in sched.get("prices") or []:
                    if isinstance(pr, dict) and pr.get("value"):
                        val = float(pr["value"]) / 100.0  # kopecks to rubles
                        if price_min is None or val < price_min:
                            price_min = val
                        if price_max is None or val > price_max:
                            price_max = val

            # Fallback if no scheduleInfo or past date: try dateReleased / dateStarted
            if not start_at or start_at < now_utc:
                continue

            # Price from Ticket objects if not in scheduleInfo
            if price_min is None:
                for t_ref in v.get("tickets") or []:
                    ref_key = t_ref.get("__ref") if isinstance(t_ref, dict) else None
                    if ref_key and ref_key in tickets_map:
                        t_obj = tickets_map[ref_key]
                        pr_range = t_obj.get("price")
                        if isinstance(pr_range, dict):
                            p_min = pr_range.get("min")
                            p_max = pr_range.get("max")
                            if isinstance(p_min, (int, float)):
                                price_min = float(p_min) / 100.0
                            if isinstance(p_max, (int, float)):
                                price_max = float(p_max) / 100.0
                            break

            # Cover Image (prefer origin / high-res)
            cover_image_url = None
            img_obj = v.get("image")
            if isinstance(img_obj, dict):
                for img_key, img_val in img_obj.items():
                    if isinstance(img_val, dict) and img_val.get("url"):
                        u = str(img_val["url"])
                        if "/orig" in u or "s760x380" in u or "s940x380" in u or not cover_image_url:
                            cover_image_url = u
                            if "/orig" in u:
                                break

            # Age restriction
            age_restriction = str(v.get("contentRating") or "").strip() or None

            # Description / Argument
            argument = str(v.get("argument") or "").strip()
            description = argument if argument else f"Мероприятие «{title}» на площадке {venue_name} в городе {default_city_id.capitalize()}."

            address = f"г. {default_city_id.capitalize()}, {venue_name}"

            # Category resolution
            inferred_rubric = default_rubric
            type_tag = v.get("type")
            if isinstance(type_tag, dict) and type_tag.get("code"):
                inferred_rubric = type_tag["code"]

            category_id = classify_event_category(
                title=title,
                description=description,
                raw_rubric=inferred_rubric,
                age_restriction=age_restriction,
                venue_name=venue_name,
            )

            events.append(AggregatedEvent(
                source_name="yandex_afisha",
                external_id=f"yandex_{ext_id}",
                source_url=source_url,
                title=title,
                description=description,
                start_at=start_at,
                city_id=default_city_id,
                venue_name=venue_name,
                address=address,
                price_min=price_min,
                price_max=price_max,
                price_currency="RUB",
                cover_image_url=cover_image_url,
                age_restriction=age_restriction,
                category_id=category_id,
            ))

        return events
