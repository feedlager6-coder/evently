import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_

from app.database import AsyncSessionLocal
from app.models.event import Event, EventStatus
from app.services.aggregator.aggregator_service import AggregatorMasterService
from app.services.aggregator.city_mapping import CITY_NAMES_RU, get_city_name_ru

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanup_and_sync")


async def main():
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        logger.info("Starting comprehensive database cleanup and sync...")

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
        past_stmt = select(Event).where(
            and_(
                Event.source_type == "external",
                Event.status != EventStatus.DELETED.value,
                Event.start_at < now,
            )
        )
        past_events = (await session.execute(past_stmt)).scalars().all()
        logger.info("Found %d past events to purge.", len(past_events))
        for ev in past_events:
            ev.status = EventStatus.DELETED.value

        # 3. Clean up broken/generic culture_ru catalog URLs that 404
        broken_cult_stmt = select(Event).where(
            and_(
                Event.source_name == "culture_ru",
                Event.status != EventStatus.DELETED.value,
                or_(
                    Event.source_url.ilike("%culture.ru/events?%"),
                    Event.source_url == "https://www.culture.ru/events",
                    Event.city_id == "makhachkala",
                )
            )
        )
        cult_events = (await session.execute(broken_cult_stmt)).scalars().all()
        logger.info("Found %d legacy / broken culture_ru events to purge.", len(cult_events))
        for ev in cult_events:
            ev.status = EventStatus.DELETED.value

        await session.commit()
        logger.info("Purge committed successfully.")

        # 4. Trigger fresh multi-platform synchronization
        logger.info("Triggering fresh multi-platform sync with exact session dates...")
        target_cities = [
            "makhachkala", "kaspiysk", "derbent", "khasavyurt", "buynaksk", "izberbash",
            "grozny", "vladikavkaz", "moscow", "spb", "kazan", "krasnodar", "sochi",
            "rostov_on_don", "yekaterinburg", "novosibirsk", "nizhny_novgorod", "samara", "ufa"
        ]
        stats = await AggregatorMasterService.sync_all_sources(
            session=session,
            target_cities=target_cities,
            max_events_per_city=50,
        )
        logger.info("Sync completed: %s", stats)

        # 5. Normalize all cover URLs and English city names for 100% compliance
        all_stmt = select(Event).where(
            Event.status == EventStatus.PUBLISHED.value
        )
        all_events = (await session.execute(all_stmt)).scalars().all()
        logger.info("Verifying 100%% photo and address integrity for %d published events...", len(all_events))

        for ev in all_events:
            # Fix covers
            if not ev.cover_image_url or "yastatic-net.ru" in ev.cover_image_url:
                cat = ev.category_id or "concerts"
                ev.cover_image_url = f"https://iventlyapp.ru/covers/{cat}.jpg"
            elif ev.cover_image_url.startswith("/"):
                ev.cover_image_url = f"https://iventlyapp.ru{ev.cover_image_url}"

            # Fix English city names
            city_ru = get_city_name_ru(ev.city_id)
            if ev.address and f"г. {ev.city_id.capitalize()}" in ev.address:
                ev.address = ev.address.replace(f"г. {ev.city_id.capitalize()}", f"г. {city_ru}")
            if ev.description and f"г. {ev.city_id.capitalize()}" in ev.description:
                ev.description = ev.description.replace(f"г. {ev.city_id.capitalize()}", f"г. {city_ru}")

            for cid_k, cru_v in CITY_NAMES_RU.items():
                if ev.address and f"г. {cid_k.capitalize()}" in ev.address:
                    ev.address = ev.address.replace(f"г. {cid_k.capitalize()}", f"г. {cru_v}")
                if ev.description and f"г. {cid_k.capitalize()}" in ev.description:
                    ev.description = ev.description.replace(f"г. {cid_k.capitalize()}", f"г. {cru_v}")

        await session.commit()
        logger.info("Final normalization committed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
