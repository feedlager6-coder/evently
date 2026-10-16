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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reclassify")

async def reclassify_events():
    async with AsyncSessionLocal() as session:
        # Fetch all events currently marked as 'other' using only needed columns
        result = await session.execute(
            select(Event.id, Event.title, Event.description, Event.venue_name)
            .where(Event.category_id == "other")
        )
        rows = result.all()
        logger.info("Found %d events with category 'other'", len(rows))

        reclassified = 0
        cat_counts = {}

        for ev_id, title, desc, venue in rows:
            # Combine title, venue name, and first 400 chars of description
            desc_words = [w.strip() for w in (desc or "")[:400].split() if len(w) > 3]
            venue_words = [w.strip() for w in (venue or "").split() if len(w) > 3]
            
            new_cat = resolve_category(
                title=title or "",
                raw_tags=desc_words + venue_words,
                raw_genres=[venue or ""],
                raw_categories=[]
            )

            if new_cat != "other":
                await session.execute(
                    update(Event).where(Event.id == ev_id).values(category_id=new_cat)
                )
                reclassified += 1
                cat_counts[new_cat] = cat_counts.get(new_cat, 0) + 1

        if reclassified > 0:
            await session.commit()
            logger.info("Successfully reclassified %d events: %s", reclassified, cat_counts)
        else:
            logger.info("No events reclassified")

        # Query full distribution
        dist_res = await session.execute(
            select(Event.category_id, func.count(Event.id))
            .group_by(Event.category_id)
            .order_by(func.count(Event.id).desc())
        )
        print("\n=== UPDATED CATEGORY DISTRIBUTION ===")
        total = 0
        for cat_id, cnt in dist_res.all():
            total += cnt
            print(f"| {cat_id:15} | {cnt:5} events |")
        print(f"Total events: {total}\n")

if __name__ == "__main__":
    asyncio.run(reclassify_events())
