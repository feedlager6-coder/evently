import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, or_

from app.database import AsyncSessionLocal
from app.models.event import Event, EventStatus
from app.services.aggregator.aggregator_service import AggregatorMasterService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanup_and_sync")


async def main():
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        logger.info("Starting database cleanup of cinema, cartoons, and past events...")

        # 1. Delete all cinema, cartoons, and movie theater screenings
        cinema_stmt = select(Event).where(
            and_(
                Event.status != EventStatus.DELETED.value,
                or_(
                    Event.category_id == "cinema",
                    Event.source_url.ilike("%/cinema/%"),
                    Event.source_url.ilike("%/kino/%"),
                    Event.source_url.ilike("%/excursions/%"),
                    Event.title.ilike("%мультфильм%"),
                    Event.title.ilike("%мультик%"),
                    Event.venue_name.ilike("%кинотеатр%"),
                    Event.venue_name.ilike("%кинозал%"),
                    Event.venue_name.ilike("%синема%"),
                    Event.venue_name.ilike("%в % кинотеатр%"),
                )
            )
        )
        cinema_events = (await session.execute(cinema_stmt)).scalars().all()
        logger.info("Found %d cinema / cartoon events to purge.", len(cinema_events))
        for ev in cinema_events:
            ev.status = EventStatus.DELETED.value

        # 2. Delete past external events
        cutoff = now
        past_stmt = select(Event).where(
            and_(
                Event.source_type == "external",
                Event.status != EventStatus.DELETED.value,
                Event.start_at < cutoff,
            )
        )
        past_events = (await session.execute(past_stmt)).scalars().all()
        logger.info("Found %d past events to purge.", len(past_events))
        for ev in past_events:
            ev.status = EventStatus.DELETED.value

        # 3. Clean up legacy culture_ru events in makhachkala that lack exact live sessions
        cult_stmt = select(Event).where(
            and_(
                Event.source_name == "culture_ru",
                Event.city_id == "makhachkala",
                Event.status != EventStatus.DELETED.value,
            )
        )
        cult_events = (await session.execute(cult_stmt)).scalars().all()
        logger.info("Found %d legacy culture_ru events in makhachkala to purge.", len(cult_events))
        for ev in cult_events:
            ev.status = EventStatus.DELETED.value

        await session.commit()
        logger.info("Cleanup committed successfully.")

        # 3. Trigger fresh synchronization with deep date extraction
        logger.info("Triggering fresh multi-platform sync with exact session dates...")
        # Focus on key Dagestan and sample cities first to verify 100% precision
        target_cities = [
            "makhachkala", "kaspiysk", "derbent", "khasavyurt", "buynaksk", "izberbash",
            "grozny", "vladikavkaz", "moscow", "saint_petersburg"
        ]
        stats = await AggregatorMasterService.sync_all_sources(
            session=session,
            target_cities=target_cities,
            max_events_per_city=40,
        )
        logger.info("Sync completed: %s", stats)


if __name__ == "__main__":
    asyncio.run(main())
