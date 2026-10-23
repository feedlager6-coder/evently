import asyncio
import httpx
from app.services.aggregator.yandex_afisha_parser import YandexAfishaParser

async def test():
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get("https://afisha.yandex.ru/makhachkala/concert")
        events = YandexAfishaParser._parse_apollo_state(resp.text, "makhachkala", "concert")
        for ev in events:
            if "shaman" in ev.title.lower() or "шахмарданов" in ev.title.lower():
                print(f"TITLE={ev.title} | START={ev.start_at} | COVER={ev.cover_image_url} | VENUE={ev.venue_name}")

asyncio.run(test())
