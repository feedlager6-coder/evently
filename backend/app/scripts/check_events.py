import asyncio
from sqlalchemy import select, and_
from app.database import AsyncSessionLocal
from app.models.event import Event, EventStatus

async def main():
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Event)
            .where(
                and_(
                    Event.city_id == "makhachkala",
                    Event.status == EventStatus.PUBLISHED.value,
                )
            )
            .order_by(Event.start_at.asc())
        )
        events = (await session.execute(stmt)).scalars().all()
        print(f"Total published in Makhachkala: {len(events)}")
        for i, ev in enumerate(events, 1):
            print(f"{i:2d}. ID={ev.id} | START={ev.start_at} | CREATED={ev.created_at} | SOURCE={ev.source_name} | URL={ev.source_url} | TITLE={ev.title}")

if __name__ == "__main__":
    asyncio.run(main())
