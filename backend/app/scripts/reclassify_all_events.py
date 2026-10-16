import asyncio
import logging
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select, func, update
from app.database import AsyncSessionLocal
from app.models.event import Event
from app.services.external_sync_service import resolve_category

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reclassify_all")


async def reclassify_all_events():
    async with AsyncSessionLocal() as session:
        # Fetch all external events across all categories
        result = await session.execute(
            select(Event.id, Event.title, Event.description, Event.venue_name, Event.category_id)
            .where(Event.source_type == "external")
        )
        rows = result.all()
        logger.info("Found %d external events to reclassify", len(rows))

        changed = 0
        from_to = {}

        for ev_id, title, desc, venue, old_cat in rows:
            new_cat = resolve_category(
                raw_cat="",
                title=title or "",
                description=(desc or "")[:400],
                venue_name=venue or "",
            )

            if new_cat != old_cat:
                await session.execute(
                    update(Event).where(Event.id == ev_id).values(category_id=new_cat)
                )
                changed += 1
                key = f"{old_cat} -> {new_cat}"
                from_to[key] = from_to.get(key, 0) + 1

        if changed > 0:
            await session.commit()
            logger.info("Successfully reclassified %d events!", changed)
            for k, count in sorted(from_to.items(), key=lambda x: -x[1]):
                logger.info("  %s: %d", k, count)
        else:
            logger.info("No category changes needed")

        # Query and log full distribution
        dist_res = await session.execute(
            select(Event.category_id, func.count(Event.id))
            .where(Event.source_type == "external")
            .group_by(Event.category_id)
            .order_by(func.count(Event.id).desc())
        )
        logger.info("New external events distribution:")
        for cat_id, cnt in dist_res.all():
            logger.info("  %-12s: %d", cat_id, cnt)


if __name__ == "__main__":
    asyncio.run(reclassify_all_events())
