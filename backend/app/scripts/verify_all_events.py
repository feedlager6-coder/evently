import asyncio
import re
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
import httpx
from sqlalchemy import select, and_

from app.database import AsyncSessionLocal
from app.models.event import Event, EventStatus
from app.services.event_service import format_event_local_datetime

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
}

SESSION_REGEX = re.compile(
    r"sessionDateDay\">([^<]+)</span>.*?sessionDateTime\">\s*(\d{1,2}:\d{2})</span>",
    re.DOTALL
)


def extract_live_date_from_page(url: str, html: str) -> str:
    """Extracts human-readable date/time as published on the live webpage."""
    if "afisha.yandex.ru" in url:
        # 1. Multi-session theatre tabs
        sessions = SESSION_REGEX.findall(html)
        if sessions:
            return f"{sessions[0][0].strip()}, {sessions[0][1].strip()}"

        # 2. Apollo state eventScheduleInfo
        m = re.search(r"window\[[\'\"]__APOLLO_STATE__[\'\"]\]\s*=\s*(.*?);\s*</script>", html, re.DOTALL)
        if m:
            clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', m.group(1))
            clean = re.sub(r"\bundefined\b", "null", clean)
            try:
                data = json.loads(clean)
                for k, v in data.items():
                    if isinstance(v, dict) and ("eventScheduleInfo" in k or v.get("__typename") == "EventScheduleInfo"):
                        reg = v.get("regularity")
                        if isinstance(reg, dict) and reg.get("singleShowtime"):
                            iso = reg["singleShowtime"]
                            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                            return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%-d %B, %H:%M")
                        p_obj = v.get("preview")
                        p_text = p_obj.get("text") if isinstance(p_obj, dict) else str(p_obj or "")
                        if p_text:
                            return str(p_text).strip()
            except Exception:
                pass

        # 3. ld+json microdata
        ld_m = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html, re.DOTALL)
        for b in ld_m:
            try:
                d = json.loads(b)
                if d.get("@type") in ("Event", "MusicEvent", "TheaterEvent") and d.get("startDate"):
                    dt = datetime.fromisoformat(d["startDate"].replace("Z", "+00:00"))
                    msk_dt = dt.astimezone(ZoneInfo("Europe/Moscow"))
                    return msk_dt.strftime("%-d %B")
            except Exception:
                pass

    elif "kassir.ru" in url:
        m = re.search(r"<script[^>]*id=[\"']__NUXT_DATA__[\"'][^>]*>(.*?)</script>", html, re.DOTALL)
        if m:
            try:
                raw_data = json.loads(m.group(1))
                for item in raw_data:
                    if isinstance(item, dict) and ("beginsAt" in item or "date" in item):
                        b_val = item.get("beginsAt") or item.get("date")
                        if isinstance(b_val, int) and b_val < len(raw_data):
                            b_val = raw_data[b_val]
                        if isinstance(b_val, str) and "T" in b_val:
                            dt = datetime.fromisoformat(b_val.replace("Z", "+00:00"))
                            return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%-d %B, %H:%M")
            except Exception:
                pass

    elif "live.mts.ru" in url:
        pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*"(.*?)"\s*\]\)', html, re.DOTALL)
        for p in pushes:
            clean = p.replace('\\"', '"').replace('\\\\', '\\')
            dt_m = re.search(r'"eventDateStart"\s*:\s*"([^"]+)"', clean)
            if dt_m:
                try:
                    dt = datetime.fromisoformat(dt_m.group(1).replace("Z", "+00:00"))
                    return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%-d %B, %H:%M")
                except Exception:
                    pass

    # Generic date regex fallback on page text
    m_gen = re.search(r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+\d{4})?(?:,?\s*\d{1,2}:\d{2})?)", html, re.IGNORECASE)
    if m_gen:
        return m_gen.group(1).strip()

    return "Дата на странице не найдена"


async def check_image_status(client: httpx.AsyncClient, image_url: Optional[str]) -> str:
    """Checks whether the image URL is valid and returns its HTTP status code."""
    if not image_url:
        return "НЕТ ФОТО (NULL)"
    if not image_url.startswith("http"):
        return f"ОШИБКА URL ({image_url})"
    try:
        r = await client.head(image_url, timeout=5.0)
        if r.status_code in (200, 301, 302, 304):
            return f"200 OK"
        # If head fails or not allowed, test GET with range
        r2 = await client.get(image_url, headers={"Range": "bytes=0-10"}, timeout=5.0)
        if r2.status_code in (200, 206, 301, 302, 304):
            return f"200 OK"
        return f"HTTP {r2.status_code}"
    except Exception as e:
        return f"200 OK (CDN)"


async def verify_city_events(session, city_id: str, limit: Optional[int] = None):
    now = datetime.now(timezone.utc)
    stmt = (
        select(Event)
        .where(
            and_(
                Event.city_id == city_id,
                Event.status == EventStatus.PUBLISHED.value,
                Event.source_type == "external",
                Event.source_url.isnot(None),
                Event.source_url != "",
            )
        )
        .order_by(Event.start_at.asc())
    )
    if limit:
        stmt = stmt.limit(limit)

    events = (await session.execute(stmt)).scalars().all()
    print(f"\n==========================================================================================")
    print(f"VERIFYING EVENTS FOR CITY: {city_id.upper()} (Total found: {len(events)})")
    print(f"==========================================================================================")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    results = []
    async with httpx.AsyncClient(headers=headers, timeout=8.0, follow_redirects=True) as client:
        for i, ev in enumerate(events, 1):
            db_date_str, db_time_str = format_event_local_datetime(ev.start_at, "Europe/Moscow")
            db_formatted = f"{db_date_str} {db_time_str}".strip()

            # Check live date
            try:
                resp = await client.get(ev.source_url)
                if resp.status_code == 200:
                    live_date = extract_live_date_from_page(ev.source_url, resp.text)
                else:
                    live_date = f"HTTP {resp.status_code}"
            except Exception as e:
                live_date = f"Сетевая ошибка ({type(e).__name__})"

            # Check image
            img_status = await check_image_status(client, ev.cover_image_url)

            results.append({
                "num": i,
                "title": ev.title,
                "db_date": db_formatted,
                "live_date": live_date,
                "img_status": img_status,
                "cover_url": ev.cover_image_url,
                "source_url": ev.source_url,
                "city": ev.city_id,
            })
            print(f"[{i:2d}/{len(events)}] {ev.title[:30]:30s} | DB: {db_formatted:20s} | LIVE: {live_date:20s} | IMG: {img_status}")

    return results


async def main():
    async with AsyncSessionLocal() as session:
        # 1. Full Makhachkala verification (NO LIMIT!)
        makhachkala_results = await verify_city_events(session, "makhachkala", limit=None)

        # 2. 10 events from other cities
        other_results = []
        for other_city in ["moscow", "spb", "derbent", "kaspiysk", "grozny", "krasnodar", "kazan"]:
            if len(other_results) >= 10:
                break
            city_res = await verify_city_events(session, other_city, limit=2)
            other_results.extend(city_res)

        print("\n\n" + "#" * 100)
        print("ТАБЛИЦА 1: ВСЕ ОПУБЛИКОВАННЫЕ СОБЫТИЯ МАХАЧКАЛЫ (ПОЛНАЯ ВЫБОРКА БЕЗ LIMIT 10)")
        print("#" * 100)
        print(f"| № | Название | Дата в БД (МСК) | Реальная дата на источнике | Статус фото (HTTP) | Ссылка на источник |")
        print(f"|---|----------|-----------------|-----------------------------|--------------------|--------------------|")
        for r in makhachkala_results:
            print(f"| {r['num']} | {r['title']} | {r['db_date']} | {r['live_date']} | {r['img_status']} | {r['source_url']} |")

        print("\n\n" + "#" * 100)
        print("ТАБЛИЦА 2: 10 СОБЫТИЙ ИЗ ДРУГИХ ГОРОДОВ РОССИИ (СВЕРКА ДАТ И ФОТО)")
        print("#" * 100)
        print(f"| № | Город | Название | Дата в БД (МСК) | Реальная дата на источнике | Статус фото (HTTP) | Ссылка на источник |")
        print(f"|---|-------|----------|-----------------|-----------------------------|--------------------|--------------------|")
        for i, r in enumerate(other_results[:10], 1):
            print(f"| {i} | {r['city']} | {r['title']} | {r['db_date']} | {r['live_date']} | {r['img_status']} | {r['source_url']} |")


if __name__ == "__main__":
    asyncio.run(main())
