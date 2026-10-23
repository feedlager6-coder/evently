import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.event import Event, EventStatus
from app.models.city import City
from app.models.category import Category
from app.models.user import User
from app.services.storage_service import storage_service
from app.services.aggregator.models import AggregatedEvent
from app.services.aggregator.kassir_parser import KassirParser
from app.services.aggregator.mts_live_parser import MtsLiveParser
from app.services.aggregator.yandex_afisha_parser import YandexAfishaParser
from app.services.aggregator.deduplication import is_cross_platform_duplicate

logger = logging.getLogger("evently.aggregator.master")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]


class AggregatorMasterService:
    """
    Master service coordinating collection, deduplication, and synchronization
    of event tickets from Kassir.ru, MTS Live, and Yandex.Afisha.
    """

    @classmethod
    async def get_curator_user_id(cls, session: AsyncSession) -> int:
        curator = (await session.execute(
            select(User).where(
                (User.telegram_id == 777000) | (User.username == "ivently_curator")
            ).order_by(User.id.asc())
        )).scalars().first()
        if curator:
            return curator.id

        admin = (await session.execute(
            select(User).order_by(User.id.asc())
        )).scalars().first()
        if admin:
            return admin.id

        new_curator = User(
            telegram_id=777000,
            username="ivently_curator",
            first_name="Афиша Ivently",
            last_name="",
            default_city_id="makhachkala",
        )
        session.add(new_curator)
        await session.commit()
        await session.refresh(new_curator)
        return new_curator.id

    @classmethod
    async def sync_all_sources(
        cls,
        session: AsyncSession,
        target_cities: Optional[List[str]] = None,
        max_events_per_city: int = 50,
        curator_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Runs multi-platform event harvesting, cross-platform fuzzy deduplication,
        and database upserting across all target cities.
        """
        now = datetime.now(timezone.utc)
        if not curator_user_id:
            curator_user_id = await cls.get_curator_user_id(session)

        # Get list of active cities in DB
        city_stmt = select(City.id).where(City.is_active == True)
        if target_cities:
            city_stmt = city_stmt.where(City.id.in_(target_cities))
        active_cities = (await session.execute(city_stmt)).scalars().all()

        headers = {
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
        }

        stats = {
            "total_harvested": 0,
            "created": 0,
            "updated": 0,
            "duplicates_merged": 0,
            "by_source": {"kassir": 0, "mts_live": 0, "yandex_afisha": 0},
            "by_category": {},
            "by_city": {},
            "errors": [],
        }

        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as http_client:
            for city_id in active_cities:
                city_events: List[AggregatedEvent] = []

                # 1. Harvest from Kassir.ru
                try:
                    k_events = await KassirParser.fetch_city_events(http_client, city_id, max_events=max_events_per_city)
                    city_events.extend(k_events)
                    stats["by_source"]["kassir"] += len(k_events)
                except Exception as e:
                    stats["errors"].append(f"Kassir {city_id}: {str(e)}")

                # 2. Harvest from MTS Live
                try:
                    m_events = await MtsLiveParser.fetch_city_events(http_client, city_id, max_events=max_events_per_city)
                    city_events.extend(m_events)
                    stats["by_source"]["mts_live"] += len(m_events)
                except Exception as e:
                    stats["errors"].append(f"MTS Live {city_id}: {str(e)}")

                # 3. Harvest from Yandex.Afisha
                try:
                    y_events = await YandexAfishaParser.fetch_city_events(http_client, city_id, max_events=max_events_per_city)
                    city_events.extend(y_events)
                    stats["by_source"]["yandex_afisha"] += len(y_events)
                except Exception as e:
                    stats["errors"].append(f"Yandex.Afisha {city_id}: {str(e)}")

                stats["total_harvested"] += len(city_events)

                # Process deduplication and database saving for this city
                for ev in city_events:
                    try:
                        async with session.begin_nested():
                            # --- STAGE 1: Exact source match ---
                            exact_stmt = select(Event).where(
                                and_(
                                    Event.source_name == ev.source_name,
                                    Event.external_id == ev.external_id,
                                )
                            )
                            existing_exact = (await session.execute(exact_stmt)).scalars().first()

                            if not existing_exact and ev.source_url:
                                url_stmt = select(Event).where(Event.source_url == ev.source_url)
                                existing_exact = (await session.execute(url_stmt)).scalars().first()

                            if existing_exact:
                                # Update fields
                                existing_exact.title = ev.title
                                if ev.price_min is not None:
                                    existing_exact.price_amount = ev.price_min
                                if ev.cover_image_url and (not existing_exact.cover_image_url or "unsplash" in existing_exact.cover_image_url):
                                    existing_exact.cover_image_url = ev.cover_image_url
                                existing_exact.start_at = ev.start_at
                                existing_exact.last_synced_at = now
                                existing_exact.status = EventStatus.PUBLISHED.value
                                stats["updated"] += 1
                                continue

                            # --- STAGE 2: Cross-platform & same-day session deduplication ---
                            ev_utc = ev.start_at.astimezone(timezone.utc)
                            day_start = datetime(ev_utc.year, ev_utc.month, ev_utc.day, 0, 0, 0, tzinfo=timezone.utc)
                            day_end = datetime(ev_utc.year, ev_utc.month, ev_utc.day, 23, 59, 59, tzinfo=timezone.utc)

                            candidate_stmt = select(Event).where(
                                and_(
                                    Event.city_id == ev.city_id,
                                    Event.start_at >= day_start,
                                    Event.start_at <= day_end,
                                    Event.status != EventStatus.DELETED.value,
                                )
                            )
                            candidates = (await session.execute(candidate_stmt)).scalars().all()

                            is_dup = False
                            matched_candidate = None
                            for cand in candidates:
                                is_d, score, reason = is_cross_platform_duplicate(
                                    title_a=ev.title,
                                    venue_a=ev.venue_name,
                                    time_a=ev.start_at,
                                    city_a=ev.city_id,
                                    title_b=cand.title,
                                    venue_b=cand.venue_name,
                                    time_b=cand.start_at,
                                    city_b=cand.city_id,
                                )
                                if is_d:
                                    is_dup = True
                                    matched_candidate = cand
                                    logger.info(
                                        "Merged cross-platform / same-day duplicate: '%s' (%s) into '%s' (%s) [score: %.2f, reason: %s]",
                                        ev.title, ev.source_name, cand.title, cand.source_name, score, reason
                                    )
                                    break

                            if is_dup and matched_candidate:
                                # Enrich existing card without creating duplicate!
                                stats["duplicates_merged"] += 1
                                if ev.price_min is not None:
                                    if matched_candidate.price_amount is None or ev.price_min < matched_candidate.price_amount:
                                        matched_candidate.price_amount = ev.price_min
                                if ev.cover_image_url and (not matched_candidate.cover_image_url or "unsplash" in matched_candidate.cover_image_url or "default" in matched_candidate.cover_image_url):
                                    matched_candidate.cover_image_url = ev.cover_image_url
                                if len(ev.description) > len(matched_candidate.description):
                                    matched_candidate.description = ev.description
                                if not matched_candidate.source_url and ev.source_url:
                                    matched_candidate.source_url = ev.source_url

                                # If upcoming, keep earlier upcoming session on that day
                                if ev.start_at >= now and matched_candidate.start_at >= now:
                                    matched_candidate.start_at = min(ev.start_at, matched_candidate.start_at)
                                elif ev.start_at >= now and matched_candidate.start_at < now:
                                    matched_candidate.start_at = ev.start_at

                                matched_candidate.last_synced_at = now
                                continue

                            # --- Not a duplicate: Insert new event card ---
                            new_event = Event(
                                title=ev.title,
                                description=ev.description,
                                cover_image_url=ev.cover_image_url,
                                category_id=ev.category_id,
                                city_id=ev.city_id,
                                start_at=ev.start_at,
                                venue_name=ev.venue_name,
                                address=ev.address,
                                latitude=ev.latitude,
                                longitude=ev.longitude,
                                price_amount=ev.price_min,
                                price_currency=ev.price_currency,
                                status=EventStatus.PUBLISHED.value,
                                organizer_user_id=curator_user_id,
                                source_type="external",
                                source_name=ev.source_name,
                                external_id=ev.external_id,
                                source_url=ev.source_url,
                                last_synced_at=now,
                                created_at=now,
                                updated_at=now,
                            )
                            session.add(new_event)
                            stats["created"] += 1

                            # Update counters
                            stats["by_category"][ev.category_id] = stats["by_category"].get(ev.category_id, 0) + 1
                            stats["by_city"][ev.city_id] = stats["by_city"].get(ev.city_id, 0) + 1

                        await session.commit()
                    except Exception as item_err:
                        logger.warning("Error upserting event %s: %s", ev.title, item_err)

                # Brief pause between cities to adhere to rate-limiting
                await asyncio.sleep(0.5)

        logger.info(
            "Aggregator sync finished: %d harvested, %d created, %d updated, %d duplicates merged",
            stats["total_harvested"], stats["created"], stats["updated"], stats["duplicates_merged"]
        )
        return stats
