import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.event import Event
import httpx
from app.services.aggregator.yandex_afisha_parser import YandexAfishaParser

async def test():
    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(Event.title.ilike("%shaman%"))
        db_shaman = (await session.execute(stmt)).scalars().first()
        if db_shaman:
            print(f"DB SHAMAN: id={db_shaman.id}, ext_id={db_shaman.external_id}, source={db_shaman.source_name}, url={db_shaman.source_url}, start={db_shaman.start_at}")

        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = await client.get("https://afisha.yandex.ru/makhachkala/concert")
            events = YandexAfishaParser._parse_apollo_state(resp.text, "makhachkala", "concert")
            for ev in events:
                if "shaman" in ev.title.lower():
                    print(f"PARSED SHAMAN: ext_id={ev.external_id}, source={ev.source_name}, url={ev.source_url}, start={ev.start_at}")

asyncio.run(test())
