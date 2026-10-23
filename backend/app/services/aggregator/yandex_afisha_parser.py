import json
import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, Set, Dict, Any, Tuple
import httpx

from app.services.aggregator.models import AggregatedEvent
from app.services.aggregator.category_classifier import classify_event_category
from app.services.aggregator.city_mapping import (
    YANDEX_CITY_SLUGS,
    resolve_city_from_text,
    validate_event_city,
)
from app.services.event_service import resolve_city_timezone

logger = logging.getLogger("evently.aggregator.yandex_afisha")

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
}

# Strictly cultural and live entertainment rubrics (NO cinema or raw index)
YANDEX_RUBRICS = [
    "theatre",    # Theatre, Opera, Ballet
    "concert",    # Concerts & Live Music
    "standup",    # Standup & Comedy
    "art",        # Exhibitions, Museums & Galleries
    "show",       # Shows, Musicals, Circus
    "kids",       # Children & Family (excluding movie cartoons)
    "sport",      # Sports events & Matches
]

SESSION_REGEX = re.compile(
    r"sessionDateDay\">([^<]+)</span>.*?sessionDateTime\">\s*(\d{1,2}:\d{2})</span>",
    re.DOTALL
)


def parse_russian_date_time(day_month_str: str, time_str: str, tz: Any) -> Optional[datetime]:
    """Parses Russian date like '27 октября' and time '18:30' into UTC datetime."""
    try:
        parts = day_month_str.strip().split()
        if len(parts) < 2:
            return None
        day = int(parts[0])
        month_name = parts[1].lower()
        if month_name not in MONTHS_RU:
            return None
        month = MONTHS_RU[month_name]

        now_local = datetime.now(tz)
        year = now_local.year
        # If month is earlier in the year than current month (e.g. January when now is October), roll over
        if month < now_local.month - 1:
            year += 1

        t_parts = time_str.strip().split(":")
        hour = int(t_parts[0])
        minute = int(t_parts[1])

        local_dt = datetime(year, month, day, hour, minute, 0, tzinfo=tz)
        return local_dt.astimezone(timezone.utc)
    except Exception:
        return None


class YandexAfishaParser:
    """
    Parser for Yandex.Afisha (afisha.yandex.ru) with deep session extraction.
    Pulls exact showtime dates from individual sessions, Apollo GraphQL cache,
    and enriches cards with full descriptions while strictly excluding cinema/cartoons.
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

        try:
            city_tz = resolve_city_timezone("Europe/Moscow")
        except Exception:
            city_tz = ZoneInfo("Europe/Moscow")

        events: List[AggregatedEvent] = []
        seen_ids: Set[str] = set()
        now_utc = datetime.now(timezone.utc)

        for rubric in YANDEX_RUBRICS:
            if len(events) >= max_events:
                break
            url = f"https://afisha.yandex.ru/{city_slug}/{rubric}"
            try:
                resp = await client.get(url, timeout=12.0)
                if resp.status_code == 403:
                    logger.warning("Yandex.Afisha returned 403 for %s/%s (WAF active)", city_slug, rubric)
                    continue
                if resp.status_code != 200:
                    continue

                extracted = cls._parse_apollo_state(
                    html=resp.text,
                    default_city_id=city_id,
                    default_rubric=rubric,
                )
                for ev in extracted:
                    if len(events) >= max_events:
                        break

                    # Deep session extraction for exact dates and rich description
                    await cls._enrich_event_details(client, ev, city_tz)

                    if not ev.start_at or ev.start_at < now_utc:
                        continue

                    if ev.external_id not in seen_ids:
                        seen_ids.add(ev.external_id)
                        events.append(ev)
            except Exception as e:
                logger.warning("Error fetching Yandex.Afisha %s/%s: %s", city_slug, rubric, e)

        logger.info("Yandex.Afisha parsed %d events for %s", len(events), city_id)
        return events

    @classmethod
    async def _enrich_event_details(
        cls,
        client: httpx.AsyncClient,
        ev: AggregatedEvent,
        city_tz: ZoneInfo,
    ) -> None:
        """Fetches the event page to extract exact session showtimes and rich description."""
        if not ev.source_url:
            return

        now_utc = datetime.now(timezone.utc)
        try:
            resp = await client.get(ev.source_url, timeout=8.0)
            if resp.status_code != 200:
                return

            ev_html = resp.text

            # 1. Exact session dates & times from HTML schedule tabs
            found_sessions = SESSION_REGEX.findall(ev_html)
            valid_sessions = []
            for s_day, s_time in found_sessions:
                dt_sess = parse_russian_date_time(s_day, s_time, city_tz)
                if dt_sess and dt_sess >= now_utc:
                    valid_sessions.append(dt_sess)

            if valid_sessions:
                valid_sessions.sort()
                ev.start_at = valid_sessions[0]

            # 2. Extract full rich description from event page Apollo state
            ev_m = re.search(r"window\[[\x27\"]__APOLLO_STATE__[\x27\"]\]\s*=\s*(.*?);\s*</script>", ev_html, re.DOTALL)
            if ev_m:
                ev_clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', ev_m.group(1))
                ev_clean = re.sub(r"\bundefined\b", "null", ev_clean)
                ev_json = json.loads(ev_clean)
                for ek, ev_val in ev_json.items():
                    if isinstance(ev_val, dict) and ev_val.get("__typename") == "Event":
                        d_text = str(ev_val.get("description") or "").strip()
                        if len(d_text) > 30:
                            ev.description = d_text
                            break
        except Exception as e:
            logger.debug("Failed deep session enrichment for %s: %s", ev.source_url, e)

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
        clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', raw)
        clean = re.sub(r"\bundefined\b", "null", clean)

        try:
            data: Dict[str, Any] = json.loads(clean)
        except Exception as e:
            logger.debug("Failed to parse Apollo JSON: %s", e)
            return []

        events: List[AggregatedEvent] = []
        now_utc = datetime.now(timezone.utc)
        city_tz = resolve_city_timezone("Europe/Moscow")

        # Lookup maps for Tickets, Places, and ScheduleInfo
        tickets_map: Dict[str, Any] = {}
        schedule_by_ref: Dict[str, Any] = {}

        # 1. Index Tickets and ActualEvent from ROOT_QUERY and Featured
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            tname = v.get("__typename")
            if tname == "Ticket":
                tickets_map[k] = v
            elif tname == "Featured" and isinstance(v.get("object"), dict):
                obj = v["object"]
                ev_ref = obj.get("event", {}).get("__ref") if isinstance(obj.get("event"), dict) else None
                sched = obj.get("scheduleInfo")
                if ev_ref and sched:
                    schedule_by_ref[ev_ref] = sched

        rq = data.get("ROOT_QUERY", {})
        if isinstance(rq, dict):
            for pk, pv in rq.items():
                if isinstance(pv, list):
                    for item in pv:
                        if isinstance(item, dict) and item.get("__typename") == "ActualEvent":
                            ev_ref = item.get("event", {}).get("__ref") if isinstance(item.get("event"), dict) else None
                            sched = item.get("scheduleInfo")
                            if ev_ref and sched:
                                schedule_by_ref[ev_ref] = sched

        # 2. Extract and enrich EventPreviews
        for k, v in data.items():
            if not isinstance(v, dict) or v.get("__typename") != "EventPreview":
                continue

            title = str(v.get("title") or "").strip()
            if not title or len(title) < 2:
                continue

            raw_url = str(v.get("url") or "").strip()
            if not raw_url:
                continue

            # Hard rejection of cinema and cartoons
            if "/cinema/" in raw_url:
                continue

            source_url = raw_url if raw_url.startswith("http") else f"https://afisha.yandex.ru{raw_url}"
            ext_id = str(v.get("id") or hash(source_url))

            # Reject cartoons and cinema keywords in title
            title_lower = title.lower()
            if any(w in title_lower for w in ["мультфильм", "мультик", "в кино"]):
                continue

            # Schedule / Date / Venue resolution
            sched = schedule_by_ref.get(k) or schedule_by_ref.get(f"Event:{ext_id}")
            start_at: Optional[datetime] = None
            venue_name = "Площадка мероприятия"
            price_min: Optional[float] = None
            price_max: Optional[float] = None

            if sched and isinstance(sched, dict):
                # A. Regularity singleShowtime e.g. "2026-11-06T18:30:00"
                reg = sched.get("regularity")
                if isinstance(reg, dict) and reg.get("singleShowtime"):
                    iso_str = str(reg["singleShowtime"]).replace('Z', '+00:00')
                    try:
                        dt_obj = datetime.fromisoformat(iso_str)
                        if dt_obj.tzinfo is None:
                            dt_obj = dt_obj.replace(tzinfo=city_tz)
                        cand_utc = dt_obj.astimezone(timezone.utc)
                        if cand_utc >= now_utc:
                            start_at = cand_utc
                    except Exception:
                        pass

                # B. Preview text if it has exact time e.g. "7 ноября, 17:00"
                if not start_at:
                    p_text = str(sched.get("preview", {}).get("text") or "")
                    tm = re.search(r"(\d{1,2}\s+[а-яё]+),\s*(\d{1,2}:\d{2})", p_text, re.IGNORECASE)
                    if tm:
                        parsed_dt = parse_russian_date_time(tm.group(1), tm.group(2), city_tz)
                        if parsed_dt and parsed_dt >= now_utc:
                            start_at = parsed_dt

                # Venue name from scheduleInfo
                if sched.get("placePreview"):
                    venue_name = str(sched["placePreview"]).strip()

                # Prices from scheduleInfo
                for pr in sched.get("prices") or []:
                    if isinstance(pr, dict) and pr.get("value"):
                        val = float(pr["value"]) / 100.0
                        if price_min is None or val < price_min:
                            price_min = val
                        if price_max is None or val > price_max:
                            price_max = val

            # Reject venue names that are movie theaters
            v_lower = venue_name.lower()
            if any(w in v_lower for w in ["кинотеатр", "кинозал", "синема", "в кино"]):
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

            # Category resolution
            inferred_rubric = default_rubric
            type_tag = v.get("type")
            type_name = ""
            if isinstance(type_tag, dict):
                if type_tag.get("code"):
                    inferred_rubric = type_tag["code"]
                if type_tag.get("name"):
                    type_name = str(type_tag["name"]).strip()

            address = f"г. {default_city_id.capitalize()}, {venue_name}"

            # Description Assembly
            raw_desc = str(v.get("description") or "").strip()
            argument = str(v.get("argument") or "").strip()
            tagline = str(v.get("tagline") or "").strip()

            if raw_desc and len(raw_desc) > 20:
                description = raw_desc
            elif argument and tagline:
                description = f"{argument}. {tagline}"
            elif argument:
                description = argument
            elif tagline:
                description = tagline
            else:
                type_label = type_name or "Культурное мероприятие"
                description = f"{type_label} «{title}». Площадка: {venue_name} ({address}). Официальные билеты онлайн на Яндекс.Афише."

            category_id = classify_event_category(
                title=title,
                description=description,
                raw_rubric=inferred_rubric,
                age_restriction=age_restriction,
                venue_name=venue_name,
                source_url=source_url,
            )

            # Strictly skip any event classified as cinema or cartoon
            if category_id == "cinema":
                continue

            # Strict Anti-Geo-Spoofing check
            if not validate_event_city(
                source_name="yandex_afisha",
                source_url=source_url,
                title=title,
                venue_name=venue_name,
                address=address,
                target_city_id=default_city_id,
            ):
                continue

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
