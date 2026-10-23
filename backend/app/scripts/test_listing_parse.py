import asyncio
from sqlalchemy import select, and_
from app.database import AsyncSessionLocal
from app.models.event import Event

async def test():
    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(and_(Event.title.ilike("%shaman%"), Event.city_id == "makhachkala"))
        db_shamans = (await session.execute(stmt)).scalars().all()
        for s in db_shamans:
            print(f"MAHACHKALA SHAMAN: id={s.id}, status={s.status}, ext_id={s.external_id}, source={s.source_name}, url={s.source_url}, start={s.start_at}, created={s.created_at}")

asyncio.run(test())
