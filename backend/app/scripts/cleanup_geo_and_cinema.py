import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Any
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.event import Event, EventStatus
from app.models.category import Category
from app.services.aggregator.city_mapping import validate_event_city
from app.services.aggregator.category_classifier import classify_event_category

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evently.cleanup")


async def run_cleanup(session: AsyncSession) -> Dict[str, Any]:
    # 1. Ensure 'cinema' category exists in DB
    cat_res = await session.execute(select(Category).where(Category.id == "cinema"))
    cinema_cat = cat_res.scalar_one_or_none()
    if not cinema_cat:
        logger.info("Creating 'cinema' category in database...")
        cinema_cat = Category(
            id="cinema",
            name="Кино",
            slug="cinema",
            is_active=True,
        )
        session.add(cinema_cat)
        await session.flush()
        logger.info("Category 'cinema' successfully created.")
    else:
        logger.info("Category 'cinema' already exists.")

    # 2. Query all published/active events
    stmt = select(Event).where(Event.status != EventStatus.DELETED.value)
    events = (await session.execute(stmt)).scalars().all()
    logger.info("Total active events before cleanup: %d", len(events))

    deleted_geo_spoofs: List[Dict[str, str]] = []
    reclassified_to_cinema = 0
    deleted_cinema_overflow = 0

    # Pass 1: Geo-Spoofing check
    surviving_events: List[Event] = []
    for ev in events:
        is_valid_city = validate_event_city(
            source_name=ev.source_name or "unknown",
            source_url=ev.source_url,
            title=ev.title,
            venue_name=ev.venue_name or "",
            address=ev.address or "",
            target_city_id=ev.city_id,
        )
        if not is_valid_city:
            deleted_geo_spoofs.append({
                "id": ev.id,
                "city": ev.city_id,
                "title": ev.title,
                "venue": ev.venue_name or "",
                "url": ev.source_url or "",
            })
            ev.status = EventStatus.DELETED.value
            logger.info(
                "GEO-LEAK PURGED: [%s] '%s' | Venue: %s | URL: %s",
                ev.city_id, ev.title, ev.venue_name, ev.source_url
            )
        else:
            surviving_events.append(ev)

    logger.info("Deleted %d foreign/geo-spoofed events from regional cities.", len(deleted_geo_spoofs))

    # Pass 2: Reclassify movies/cartoons to 'cinema'
    cinema_by_city: Dict[str, List[Event]] = defaultdict(list)
    for ev in surviving_events:
        new_cat = classify_event_category(
            title=ev.title,
            description=ev.description or "",
            raw_rubric=None,
            venue_name=ev.venue_name or "",
            source_url=ev.source_url,
        )
        if new_cat == "cinema":
            if ev.category_id != "cinema":
                logger.info("RECLASSIFIED TO CINEMA: [%s] '%s' (%s -> cinema)", ev.city_id, ev.title, ev.category_id)
                ev.category_id = "cinema"
                reclassified_to_cinema += 1
            cinema_by_city[ev.city_id].append(ev)

    # Pass 3: Limit cinema events to at most 8 per city to prevent cluttering live cultural events
    MAX_CINEMA_PER_CITY = 8
    for city_id, c_events in cinema_by_city.items():
        if len(c_events) > MAX_CINEMA_PER_CITY:
            # Sort by start_at ascending (keep closest upcoming)
            c_events.sort(key=lambda x: x.start_at)
            for excess_ev in c_events[MAX_CINEMA_PER_CITY:]:
                excess_ev.status = EventStatus.DELETED.value
                deleted_cinema_overflow += 1
                logger.info("CINEMA OVERFLOW REMOVED: [%s] '%s'", city_id, excess_ev.title)

    await session.commit()
    logger.info("Cleanup committed successfully.")

    # 3. Compute final metrics
    cat_counts_res = await session.execute(text("""
        SELECT category_id, count(*) as cnt
        FROM events
        WHERE status = 'published'
        GROUP BY category_id
        ORDER BY cnt DESC;
    """))
    categories_distribution = dict(cat_counts_res.fetchall())

    makhachkala_res = await session.execute(text("""
        SELECT title, category_id, venue_name, address, source_url
        FROM events
        WHERE city_id = 'makhachkala' AND status = 'published'
        ORDER BY start_at ASC
        LIMIT 15;
    """))
    makhachkala_sample = [dict(r._mapping) for r in makhachkala_res.fetchall()]

    moscow_leaks_res = await session.execute(text("""
        SELECT count(*)
        FROM events
        WHERE city_id != 'moscow'
          AND status = 'published'
          AND (title ILIKE '%москва 202%' OR address ILIKE '%москва%' OR venue_name ILIKE '%лужники%' OR venue_name ILIKE '%ирины винер%');
    """))
    residual_moscow_leaks = moscow_leaks_res.scalar() or 0

    return {
        "deleted_geo_spoofs_count": len(deleted_geo_spoofs),
        "reclassified_to_cinema": reclassified_to_cinema,
        "deleted_cinema_overflow": deleted_cinema_overflow,
        "residual_moscow_leaks": residual_moscow_leaks,
        "categories_distribution": categories_distribution,
        "makhachkala_sample": makhachkala_sample,
    }


async def main():
    async with AsyncSessionLocal() as session:
        report = await run_cleanup(session)
        import json
        print("\n=== CLEANUP REPORT ===")
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
