import asyncio
import re
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
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
    """Extracts human-readable date/time as written on the live webpage."""
    if "afisha.yandex.ru" in url:
        # Check sessions
        sessions = SESSION_REGEX.findall(html)
        if sessions:
            # e.g. "27 октября 18:30"
            return f"{sessions[0][0].strip()} {sessions[0][1].strip()}"
        # Check Apollo state singleShowtime or preview
        m = re.search(r"window\[[\'\"]__APOLLO_STATE__[\'\"]\]\s*=\s*(.*?);\s*</script>", html, re.DOTALL)
        if m:
            clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', m.group(1))
            clean = re.sub(r"\bundefined\b", "null", clean)
            try:
                data = json.loads(clean)
                for k, v in data.items():
                    if isinstance(v, dict):
                        reg = v.get("regularity")
                        if isinstance(reg, dict) and reg.get("singleShowtime"):
                            iso = reg["singleShowtime"]
                            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                            return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d %B %H:%M")
                        p_text = v.get("preview", {}).get("text") if isinstance(v.get("preview"), dict) else None
                        if p_text:
                            return p_text
            except Exception:
                pass

    elif "kassir.ru" in url:
        # Nuxt data beginsAt
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
                            return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d %B %H:%M")
            except Exception:
                pass

    # Generic date regex fallback on page text
    m_gen = re.search(r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+\d{4})?(?:,?\s*\d{1,2}:\d{2})?)", html, re.IGNORECASE)
    if m_gen:
        return m_gen.group(1).strip()

    return "Дата на странице не найдена"


async def main():
    async with AsyncSessionLocal() as session:
        # Select published events in Makhachkala with external source_url
        stmt = (
            select(Event)
            .where(
                and_(
                    Event.city_id == "makhachkala",
                    Event.status == EventStatus.PUBLISHED.value,
                    Event.source_url.isnot(None),
                    Event.source_url != "",
                )
            )
            .order_by(Event.start_at.asc())
        )
        events = (await session.execute(stmt)).scalars().all()
        print(f"Total published external events in Makhachkala: {len(events)}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }

        verified_results = []

        async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
            for ev in events:
                if len(verified_results) >= 10:
                    break

                # Exclude cinema
                if ev.category_id == "cinema" or "/cinema/" in (ev.source_url or ""):
                    continue

                db_date_str, db_time_str = format_event_local_datetime(ev.start_at, "Europe/Moscow")
                db_formatted = f"{db_date_str} {db_time_str}".strip()

                try:
                    resp = await client.get(ev.source_url)
                    if resp.status_code == 200:
                        live_date = extract_live_date_from_page(ev.source_url, resp.text)
                    else:
                        live_date = f"HTTP {resp.status_code}"
                except Exception as e:
                    live_date = f"Error: {e}"

                verified_results.append({
                    "title": ev.title,
                    "db_date": db_formatted,
                    "live_date": live_date,
                    "source_url": ev.source_url,
                    "source_name": ev.source_name,
                    "category": ev.category_id,
                    "desc_len": len(ev.description or ""),
                    "desc_preview": (ev.description or "")[:120] + "..."
                })

        print("\n=== VERIFICATION RESULTS TABLE (MAKHACHKALA) ===")
        print(f"| № | Название события | start_date в нашей БД | Реальная дата на сайте-источнике | source_url | Описание (символов) |")
        print(f"|---|------------------|-----------------------|----------------------------------|------------|---------------------|")
        for i, item in enumerate(verified_results, 1):
            print(f"| {i} | {item['title']} | {item['db_date']} | {item['live_date']} | {item['source_url']} | {item['desc_len']} симв. |")

        print("\n=== DETAILED EVENT CARDS INSPECTION ===")
        for i, item in enumerate(verified_results, 1):
            print(f"\n[{i}] {item['title']}")
            print(f"    Категория: {item['category']} | Источник: {item['source_name']}")
            print(f"    Дата в БД: {item['db_date']}")
            print(f"    Дата на сайте: {item['live_date']}")
            print(f"    URL: {item['source_url']}")
            print(f"    Описание ({item['desc_len']} симв): {item['desc_preview']}")


if __name__ == "__main__":
    asyncio.run(main())
