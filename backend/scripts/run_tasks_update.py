import asyncio
import logging
import sys
from sqlalchemy import select, func, text
from app.database import AsyncSessionLocal
from app.seeds.seed_data import seed_database
from app.services.external_sync_service import ExternalSyncService
from app.models.event import Event
from app.models.city import City
from app.models.category import Category

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tasks_update")


async def main():
    logger.info("=== STEP 1: Seeding categories and activating 34 cities ===")
    async with AsyncSessionLocal() as session:
        await seed_database(session)
        logger.info("Seed database completed.")

        # Clean HTML prefix from descriptions
        logger.info("=== STEP 2: Cleaning technical HTML prefixes from descriptions ===")
        res = await session.execute(
            text(
                "UPDATE events SET description = regexp_replace(description, '^\\s*(?i:html)\\s*[:\\-]?\\s*', '') "
                "WHERE description ~* '^\\s*html\\b'"
            )
        )
        await session.commit()
        logger.info("Cleaned HTML prefix on existing events, rowcount: %s", res.rowcount)

        # Sync external events
        logger.info("=== STEP 3: Ingesting events across all 34 active cities ===")
        sync_result = await ExternalSyncService.sync_external_events(session=session)
        logger.info("Sync result: %s", sync_result)

        # Report 1: Cities and event counts
        logger.info("=== STEP 4: Generating City Event Counts Report ===")
        active_cities_stmt = select(City).where(City.is_active == True).order_by(City.name.asc())
        cities = (await session.execute(active_cities_stmt)).scalars().all()

        print("\n--- CITY EVENT COUNTS ---")
        print(f"{'#':<3} | {'City ID':<22} | {'City Name':<20} | {'Events Count':<12}")
        print("-" * 65)

        total_events = 0
        zero_cities = []
        for idx, city in enumerate(cities, start=1):
            count_stmt = select(func.count(Event.id)).where(Event.city_id == city.id, Event.status == "published")
            count = (await session.execute(count_stmt)).scalar() or 0
            total_events += count
            if count == 0:
                zero_cities.append(city.name)
            print(f"{idx:<3} | {city.id:<22} | {city.name:<20} | {count:<12}")

        print("-" * 65)
        print(f"Total Active Cities: {len(cities)}, Total Published Events: {total_events}")
        if zero_cities:
            print(f"WARNING: Cities with 0 events: {', '.join(zero_cities)}")
        else:
            print("SUCCESS: 0 empty cities! Every active city has published events.")

        # Report 2: Category distribution
        logger.info("=== STEP 5: Generating Category Distribution Report ===")
        cats_stmt = select(Category).order_by(Category.name.asc())
        categories = (await session.execute(cats_stmt)).scalars().all()

        print("\n--- CATEGORY DISTRIBUTION ---")
        print(f"{'#':<3} | {'Category ID':<16} | {'Category Name':<22} | {'Events Count':<12}")
        print("-" * 60)
        for idx, cat in enumerate(categories, start=1):
            cat_count_stmt = select(func.count(Event.id)).where(Event.category_id == cat.id, Event.status == "published")
            cat_count = (await session.execute(cat_count_stmt)).scalar() or 0
            print(f"{idx:<3} | {cat.id:<16} | {cat.name:<22} | {cat_count:<12}")
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
