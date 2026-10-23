import asyncio
import httpx
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.services.aggregator.yandex_afisha_parser import YandexAfishaParser

async def test():
    city_tz = ZoneInfo("Europe/Moscow")
    now_utc = datetime.now(timezone.utc)
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get("https://afisha.yandex.ru/makhachkala/concert")
        extracted = YandexAfishaParser._parse_apollo_state(resp.text, "makhachkala", "concert")
        print(f"Extracted {len(extracted)} events from makhachkala/concert:")
        for ev in extracted:
            pre_start = ev.start_at
            await YandexAfishaParser._enrich_event_details(client, ev, city_tz)
            post_start = ev.start_at
            print(f"  {ev.title}: pre={pre_start} -> post={post_start} | cover={ev.cover_image_url}")

asyncio.run(test())
