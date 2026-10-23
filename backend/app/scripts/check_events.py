import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.event import Event

async def main():
    async with AsyncSessionLocal() as session:
        stmt = select(Event).where(Event.city_id == "makhachkala")
        events = (await session.execute(stmt)).scalars().all()
        for ev in events:
            if "Грозный" in ev.title or "Лунь" in ev.title:
                print(f"ID={ev.id} | TITLE={ev.title} | START={ev.start_at} | SOURCE={ev.source_name} | URL={ev.source_url} | STATUS={ev.status} | CREATED={ev.created_at}")

if __name__ == "__main__":
    asyncio.run(main())
