import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure app package is importable
from app.database import AsyncSessionLocal
from app.models.event import Event, EventStatus
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.services.aggregator.deduplication import is_cross_platform_duplicate
from app.services.aggregator.category_classifier import classify_event_category

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deduplicate_events")


async def run_deduplication_and_category_fix(dry_run: bool = False):
    """
    Scans existing database events, merges cross-platform duplicates,
    preserves user bookmarks/attendance, and re-classifies categories.
    """
    logger.info("Starting database deduplication and category fix (dry_run=%s)...", dry_run)
    now_utc = datetime.now(timezone.utc)

    merged_duplicates = 0
    reclassified_categories = 0
    total_events_scanned = 0

    async with AsyncSessionLocal() as session:
        # 1. Fetch all active/published future events
        stmt = select(Event).where(
            Event.status != EventStatus.DELETED.value,
            Event.start_at >= now_utc - timedelta(hours=6),
        ).order_by(Event.city_id, Event.start_at.asc())
        events = (await session.execute(stmt)).scalars().all()
        total_events_scanned = len(events)
        logger.info("Found %d future events to check across all cities", total_events_scanned)

        # Group by city_id
        events_by_city = {}
        for ev in events:
            events_by_city.setdefault(ev.city_id, []).append(ev)

        deleted_ids = set()

        for city_id, city_evs in events_by_city.items():
            n = len(city_evs)
            for i in range(n):
                ev_a = city_evs[i]
                if ev_a.id in deleted_ids:
                    continue

                for j in range(i + 1, n):
                    ev_b = city_evs[j]
                    if ev_b.id in deleted_ids:
                        continue

                    # If difference in calendar date > same day (and > 4 hours crossing midnight), break
                    dt_a = ev_a.start_at.astimezone(timezone.utc)
                    dt_b = ev_b.start_at.astimezone(timezone.utc)
                    if dt_b.date() > dt_a.date() and (ev_b.start_at - ev_a.start_at).total_seconds() > 4 * 3600:
                        break

                    is_dup, score, reason = is_cross_platform_duplicate(
                        title_a=ev_a.title,
                        venue_a=ev_a.venue_name,
                        time_a=ev_a.start_at,
                        city_a=ev_a.city_id,
                        title_b=ev_b.title,
                        venue_b=ev_b.venue_name,
                        time_b=ev_b.start_at,
                        city_b=ev_b.city_id,
                    )

                    if is_dup:
                        logger.info(
                            "Found duplicate in %s: '%s' (id: %s, src: %s) <=> '%s' (id: %s, src: %s) [score: %.2f, reason: %s]",
                            city_id, ev_a.title, ev_a.id, ev_a.source_name, ev_b.title, ev_b.id, ev_b.source_name, score, reason
                        )

                        # Decide canonical vs duplicate:
                        # Prefer user-created event over external, or richer event
                        canonical = ev_a
                        duplicate = ev_b
                        if ev_a.source_type == "external" and ev_b.source_type == "user":
                            canonical, duplicate = ev_b, ev_a

                        # Merge start_at for same-day sessions: keep earlier upcoming session
                        if ev_a.start_at >= now_utc and ev_b.start_at >= now_utc:
                            canonical.start_at = min(ev_a.start_at, ev_b.start_at)
                        elif ev_b.start_at >= now_utc and ev_a.start_at < now_utc:
                            canonical.start_at = ev_b.start_at

                        # Merge metadata into canonical
                        if duplicate.price_amount is not None:
                            if canonical.price_amount is None or duplicate.price_amount < canonical.price_amount:
                                canonical.price_amount = duplicate.price_amount

                        if duplicate.cover_image_url and (not canonical.cover_image_url or "default" in canonical.cover_image_url or "unsplash" in canonical.cover_image_url):
                            canonical.cover_image_url = duplicate.cover_image_url

                        if len(duplicate.description) > len(canonical.description):
                            canonical.description = duplicate.description

                        if not canonical.source_url and duplicate.source_url:
                            canonical.source_url = duplicate.source_url

                        deleted_ids.add(duplicate.id)
                        merged_duplicates += 1

                        if not dry_run:
                            # Re-link attendees to canonical if not already attending
                            existing_att_ids = (await session.execute(
                                select(EventAttendee.user_id).where(EventAttendee.event_id == canonical.id)
                            )).scalars().all()

                            # Delete duplicate attendees where user is already registered for canonical
                            if existing_att_ids:
                                await session.execute(
                                    delete(EventAttendee).where(
                                        EventAttendee.event_id == duplicate.id,
                                        EventAttendee.user_id.in_(existing_att_ids)
                                    )
                                )
                            # Re-assign remaining attendees
                            await session.execute(
                                update(EventAttendee).where(EventAttendee.event_id == duplicate.id).values(event_id=canonical.id)
                            )

                            # Re-link interests (bookmarks) to canonical if not already bookmarked
                            existing_int_ids = (await session.execute(
                                select(EventInterest.user_id).where(EventInterest.event_id == canonical.id)
                            )).scalars().all()
                            if existing_int_ids:
                                await session.execute(
                                    delete(EventInterest).where(
                                        EventInterest.event_id == duplicate.id,
                                        EventInterest.user_id.in_(existing_int_ids)
                                    )
                                )
                            await session.execute(
                                update(EventInterest).where(EventInterest.event_id == duplicate.id).values(event_id=canonical.id)
                            )

                            # Delete duplicate event
                            await session.delete(duplicate)

        # 2. Fix and reclassify categories for all remaining active events
        for ev in events:
            if ev.id in deleted_ids:
                continue

            inferred_rubric = ev.category_id
            if ev.source_url:
                s_url = ev.source_url.lower()
                if any(x in s_url for x in ["/koncert", "/concert", "/music", "/muz"]):
                    inferred_rubric = "concert"
                elif any(x in s_url for x in ["/teatr", "/theater"]):
                    inferred_rubric = "theatre"
                elif any(x in s_url for x in ["/standup", "/comedy"]):
                    inferred_rubric = "standup"
                elif any(x in s_url for x in ["/art", "/muzej", "/muzei", "/vystavk", "/exhibition", "/museum"]):
                    inferred_rubric = "exhibitions"
                elif any(x in s_url for x in ["/ekskurs", "/seminar", "/education", "/lecture"]):
                    inferred_rubric = "education"
                elif any(x in s_url for x in ["/sport"]):
                    inferred_rubric = "sport"
                elif any(x in s_url for x in ["/detyam", "/kids", "/children"]):
                    inferred_rubric = "kids"
                elif any(x in s_url for x in ["/shou", "/show"]):
                    inferred_rubric = "show"

            new_cat = classify_event_category(
                title=ev.title,
                description=ev.description,
                raw_rubric=inferred_rubric,
                venue_name=ev.venue_name,
            )

            if new_cat != ev.category_id and new_cat in ["theatre", "concerts", "parties", "sports", "education", "business", "exhibitions", "other"]:
                logger.info("Reclassifying '%s' (%s): %s -> %s", ev.title, ev.id, ev.category_id, new_cat)
                reclassified_categories += 1
                if not dry_run:
                    ev.category_id = new_cat

        if not dry_run:
            await session.commit()
            logger.info("Committed changes to database.")

        logger.info(
            "Deduplication complete: Scanned %d events, merged %d duplicates, reclassified %d categories.",
            total_events_scanned, merged_duplicates, reclassified_categories
        )

    return {
        "scanned": total_events_scanned,
        "duplicates_merged": merged_duplicates,
        "reclassified": reclassified_categories,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    asyncio.run(run_deduplication_and_category_fix(dry_run=is_dry))
