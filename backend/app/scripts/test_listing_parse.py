import asyncio
import httpx
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.services.aggregator.yandex_afisha_parser import YandexAfishaParser

async def test():
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        events = await YandexAfishaParser.fetch_city_events(client, "makhachkala", max_events=100)
        print(f"FETCHED {len(events)} events for Makhachkala:")
        for ev in events:
            print(f"  [{ev.category_id}] {ev.title} | {ev.start_at} | {ev.source_url}")

asyncio.run(test())
