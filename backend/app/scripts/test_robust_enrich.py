import asyncio
import re
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import httpx

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
}

CITY_NAMES_RU = {
    "makhachkala": "Махачкала",
    "kaspiysk": "Каспийск",
    "derbent": "Дербент",
    "khasavyurt": "Хасавюрт",
    "buynaksk": "Буйнакск",
    "izberbash": "Избербаш",
    "grozny": "Грозный",
    "vladikavkaz": "Владикавказ",
    "nalchik": "Нальчик",
    "pyatigorsk": "Пятигорск",
    "stavropol": "Ставрополь",
    "moscow": "Москва",
    "spb": "Санкт-Петербург",
    "saint_petersburg": "Санкт-Петербург",
    "kazan": "Казань",
    "krasnodar": "Краснодар",
    "sochi": "Сочи",
}

def parse_date_and_time(day_str: str, month_str: str, time_str: str, tz: ZoneInfo) -> datetime:
    day = int(day_str)
    month = MONTHS_RU[month_str.lower()]
    now_local = datetime.now(tz)
    year = now_local.year
    if month < now_local.month - 1:
        year += 1
    t_parts = time_str.split(":")
    h, m = int(t_parts[0]), int(t_parts[1])
    local_dt = datetime(year, month, day, h, m, 0, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)

def enrich_from_html(url: str, html: str, city_tz: ZoneInfo):
    now_utc = datetime.now(timezone.utc)
    start_at = None
    cover_image_url = None
    venue_name = None
    address = None
    description = None

    # 1. Microdata application/ld+json
    ld_blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    for b in ld_blocks:
        try:
            d = json.loads(b)
            if isinstance(d, dict) and d.get("@type") in (
                "Event", "MusicEvent", "TheaterEvent", "VisualArtsEvent", 
                "SportsEvent", "DanceEvent", "Festival", "ExhibitionEvent"
            ):
                if d.get("startDate"):
                    raw_sd = str(d["startDate"]).replace("Z", "+00:00")
                    try:
                        parsed_sd = datetime.fromisoformat(raw_sd)
                        if parsed_sd.tzinfo is None:
                            parsed_sd = parsed_sd.replace(tzinfo=city_tz)
                        cand_utc = parsed_sd.astimezone(timezone.utc)
                        # Notice: if it's 21:00 UTC (i.e. midnight 00:00 local), the time is placeholder
                        local_cand = cand_utc.astimezone(city_tz)
                        if local_cand.hour == 0 and local_cand.minute == 0:
                            # It's date only! Keep cand_utc as fallback date
                            start_at = cand_utc
                        elif cand_utc >= now_utc:
                            start_at = cand_utc
                    except Exception:
                        pass

                # Image from ld+json
                img_val = d.get("image")
                if isinstance(img_val, str) and img_val.startswith("http") and "yastatic-net" not in img_val:
                    cover_image_url = img_val
                elif isinstance(img_val, dict) and img_val.get("url"):
                    u = str(img_val["url"])
                    if u.startswith("http") and "yastatic-net" not in u:
                        cover_image_url = u
                elif isinstance(img_val, list) and img_val:
                    u = str(img_val[0])
                    if u.startswith("http") and "yastatic-net" not in u:
                        cover_image_url = u

                # Description from ld+json
                if d.get("description"):
                    description = str(d["description"]).strip()

                # Location from ld+json
                loc = d.get("location")
                if isinstance(loc, dict):
                    if loc.get("name"):
                        venue_name = str(loc["name"]).strip()
                    addr = loc.get("address")
                    if isinstance(addr, dict) and addr.get("streetAddress"):
                        locality = addr.get("addressLocality") or "Махачкала"
                        address = f"г. {locality}, {addr['streetAddress']}"
        except Exception:
            pass

    # 2. og:image
    if not cover_image_url or "yastatic-net" in cover_image_url:
        og_m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if og_m and og_m.group(1).startswith("http") and "yastatic-net" not in og_m.group(1):
            cover_image_url = og_m.group(1)

    # 3. Targeted Apollo state for SchedulePreview & Session times
    ev_m = re.search(r"window\[[\x27\"]__APOLLO_STATE__[\x27\"]\]\s*=\s*(.*?);\s*</script>", html, re.DOTALL)
    if ev_m:
        clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', ev_m.group(1))
        clean = re.sub(r"\bundefined\b", "null", clean)
        try:
            ap_data = json.loads(clean)
            for k, v in ap_data.items():
                if isinstance(v, dict):
                    # Check schedule preview
                    for p_key, p_val in v.items():
                        if "preview" in p_key and isinstance(p_val, dict):
                            p_text = str(p_val.get("text") or "")
                            tm = re.search(r"(\d{1,2})\s+([а-яё]+),\s*(\d{1,2}:\d{2})", p_text, re.IGNORECASE)
                            if tm:
                                cand = parse_date_and_time(tm.group(1), tm.group(2), tm.group(3), city_tz)
                                if cand >= now_utc:
                                    start_at = cand
                                    break
                    if v.get("placePreview") and not venue_name:
                        venue_name = str(v["placePreview"]).strip()
        except Exception:
            pass

    # 4. Multi-session schedule tabs on theatre pages
    session_regex = re.compile(r"sessionDateDay\">([^<]+)</span>.*?sessionDateTime\">\s*(\d{1,2}:\d{2})</span>", re.DOTALL)
    found_sessions = session_regex.findall(html)
    valid_sessions = []
    for s_day_raw, s_time in found_sessions:
        parts = s_day_raw.strip().split()
        if len(parts) >= 2 and parts[1].lower() in MONTHS_RU:
            dt_cand = parse_date_and_time(parts[0], parts[1], s_time, city_tz)
            if dt_cand >= now_utc:
                valid_sessions.append(dt_cand)
    if valid_sessions:
        valid_sessions.sort()
        start_at = valid_sessions[0]

    return {
        "start_at": start_at,
        "cover_image_url": cover_image_url,
        "venue_name": venue_name,
        "address": address,
        "description": description[:100] if description else None
    }

async def test():
    city_tz = ZoneInfo("Europe/Moscow")
    urls = [
        "https://afisha.yandex.ru/makhachkala/concert/shaman-30-let-na-stsene",
        "https://afisha.yandex.ru/makhachkala/concert/arslan-shakhmardanov",
        "https://afisha.yandex.ru/makhachkala/theatre_show/sluga-dvukh-gospod-rus-dram-teatr-gorkogo"
    ]
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        for u in urls:
            resp = await client.get(u)
            res = enrich_from_html(u, resp.text, city_tz)
            local_str = res["start_at"].astimezone(city_tz).strftime("%d %B %H:%M") if res["start_at"] else "NONE"
            print(f"\nURL: {u}")
            print(f"  START (UTC): {res['start_at']} -> LOCAL: {local_str}")
            print(f"  VENUE: {res['venue_name']}")
            print(f"  ADDR: {res['address']}")
            print(f"  IMAGE: {res['cover_image_url']}")

asyncio.run(test())
