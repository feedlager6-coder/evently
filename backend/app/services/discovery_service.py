import logging
from typing import Optional, List, Tuple, Dict, Any, Set
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, distinct
from sqlalchemy.orm import selectinload

from app.models.event import Event, EventStatus
from app.models.organization import Organization, OrganizationStatus
from app.models.city import City
from app.models.category import Category
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.subscription import Subscription
from app.schemas.event import EventSummary
from app.schemas.organization import OrganizationSummary
from app.schemas.discovery import VenueSummary, UnifiedDiscoveryResponse

logger = logging.getLogger("evently.discovery")

# Transliteration mapping: Latin to Cyrillic for query tolerance
LATIN_TO_CYRILLIC_CITIES = {
    "makhachkala": "махачкала",
    "kaspiysk": "каспийск",
    "derbent": "дербент",
    "khasavyurt": "хасавюрт",
    "izberbash": "избербаш",
    "grozny": "грозный",
    "vladikavkaz": "владикавказ",
    "nalchik": "нальчик",
    "pyatigorsk": "пятигорск",
    "stavropol": "ставрополь",
    "moscow": "москва",
    "spb": "санкт-петербург",
    "kazan": "казань",
    "krasnodar": "краснодар",
    "sochi": "сочи",
    "rostov_on_don": "ростов-на-дону",
    "volgograd": "волгоград",
    "samara": "самара",
    "nizhny_novgorod": "нижний новгород",
    "ufa": "уфа",
    "perm": "пермь",
    "yekaterinburg": "екатеринбург",
    "chelyabinsk": "челябинск",
    "tyumen": "тюмень",
    "omsk": "омск",
    "novosibirsk": "новосибирск",
    "krasnoyarsk": "красноярск",
    "vladivostok": "владивосток",
    "kaliningrad": "калининград",
}

MULTI_CHAR_MAP = [
    ("shch", "щ"), ("sh", "ш"), ("ch", "ч"), ("zh", "ж"),
    ("kh", "х"), ("ts", "ц"), ("yu", "ю"), ("ya", "я"),
    ("yo", "ё"),
]

SINGLE_CHAR_MAP = {
    'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
    'z': 'з', 'i': 'и', 'y': 'й', 'k': 'к', 'l': 'л', 'm': 'м',
    'n': 'н', 'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т',
    'u': 'у', 'f': 'ф',
}


def transliterate_latin_to_cyrillic(text: str) -> Optional[str]:
    """Transliterates common Latin input to Russian Cyrillic phonetically."""
    raw = text.strip().lower()
    if not raw or not raw.isascii():
        return None

    # Check known cities first
    if raw in LATIN_TO_CYRILLIC_CITIES:
        return LATIN_TO_CYRILLIC_CITIES[raw]

    res = raw
    for multi, cyr in MULTI_CHAR_MAP:
        res = res.replace(multi, cyr)
    chars = []
    for c in res:
        chars.append(SINGLE_CHAR_MAP.get(c, c))
    translit = "".join(chars)
    return translit if translit != raw else None


class DiscoveryService:
    """
    Unified Discovery Service for Events, Organizations, and Venues.
    Guarantees zero N+1 database queries via optimized subquery aggregations.
    Strictly filters out non-public and draft entities.
    """

    @staticmethod
    async def search_events(
        session: AsyncSession,
        query: str,
        city_id: Optional[str] = None,
        category_id: Optional[str] = None,
        current_user_id: Optional[int] = None,
        limit: int = 15,
        translit_term: Optional[str] = None
    ) -> Tuple[List[EventSummary], int]:
        """Searches published events matching text query."""
        clean_q = query.strip()
        term = f"%{clean_q}%"

        # Attendee count subquery (No N+1)
        attendee_count_subq = (
            select(func.count(EventAttendee.user_id))
            .where(EventAttendee.event_id == Event.id)
            .scalar_subquery()
        )

        # Interest count subquery (No N+1)
        interest_count_subq = (
            select(func.count(EventInterest.id))
            .where(EventInterest.event_id == Event.id)
            .scalar_subquery()
        )

        stmt = (
            select(
                Event,
                Category.name.label("category_name"),
                City.name.label("city_name"),
                City.timezone.label("city_timezone"),
                attendee_count_subq.label("attendee_count"),
                interest_count_subq.label("interest_count"),
                Organization.name.label("org_name"),
                Organization.category.label("org_category"),
                Organization.avatar_url.label("org_avatar")
            )
            .join(Category, Event.category_id == Category.id)
            .join(City, Event.city_id == City.id)
            .outerjoin(Organization, Event.organization_id == Organization.id)
            .where(Event.status == EventStatus.PUBLISHED.value)
        )

        if city_id:
            stmt = stmt.where(Event.city_id == city_id)
        if category_id:
            stmt = stmt.where(Event.category_id == category_id)

        # Build search predicate
        match_conditions = [
            Event.title.ilike(term),
            Event.description.ilike(term),
            Event.venue_name.ilike(term),
            Event.address.ilike(term),
            Category.name.ilike(term),
            City.name.ilike(term),
        ]
        if translit_term:
            t_term = f"%{translit_term}%"
            match_conditions.extend([
                Event.title.ilike(t_term),
                Event.description.ilike(t_term),
                Event.venue_name.ilike(t_term),
                City.name.ilike(t_term),
            ])

        stmt = stmt.where(or_(*match_conditions))
        stmt = stmt.order_by(Event.start_at.asc())

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # Limit
        stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).all()

        # Pre-fetch user RSVP & interest event IDs if authenticated
        attending_event_ids: Set[str] = set()
        interested_event_ids: Set[str] = set()
        if current_user_id and rows:
            event_ids = [r[0].id for r in rows]
            user_att_q = select(EventAttendee.event_id).where(
                and_(EventAttendee.user_id == current_user_id, EventAttendee.event_id.in_(event_ids))
            )
            att_res = await session.execute(user_att_q)
            attending_event_ids = set(att_res.scalars().all())

            user_int_q = select(EventInterest.event_id).where(
                and_(EventInterest.user_id == current_user_id, EventInterest.event_id.in_(event_ids))
            )
            int_res = await session.execute(user_int_q)
            interested_event_ids = set(int_res.scalars().all())

        summaries: List[EventSummary] = []
        for ev, cat_name, c_name, c_tz, att_count, int_count, org_name, org_cat, org_avatar in rows:
            summaries.append(
                EventSummary(
                    id=ev.id,
                    title=ev.title,
                    cover_image_url=ev.cover_image_url,
                    category_id=ev.category_id,
                    category_name=cat_name,
                    city_id=ev.city_id,
                    city_name=c_name,
                    start_at=ev.start_at,
                    venue_name=ev.venue_name,
                    latitude=ev.latitude,
                    longitude=ev.longitude,
                    price_amount=ev.price_amount,
                    price_currency=ev.price_currency,
                    is_free=ev.price_amount is None or ev.price_amount == 0,
                    attendee_count=att_count or 0,
                    status=ev.status,
                    is_attending=ev.id in attending_event_ids,
                    interest_count=int_count or 0,
                    current_user_interested=ev.id in interested_event_ids,
                    organization_id=ev.organization_id,
                    organization_name=org_name,
                    organization_category=org_cat,
                    organization_avatar_url=org_avatar
                )
            )

        return summaries, total

    @staticmethod
    async def search_organizations(
        session: AsyncSession,
        query: str,
        city_id: Optional[str] = None,
        current_user_id: Optional[int] = None,
        limit: int = 10,
        translit_term: Optional[str] = None
    ) -> Tuple[List[OrganizationSummary], int]:
        """Searches active organizations matching text query."""
        clean_q = query.strip()
        term = f"%{clean_q}%"

        # Followers count subquery (No N+1)
        followers_subq = (
            select(func.count(Subscription.id))
            .where(Subscription.organization_id == Organization.id)
            .scalar_subquery()
        )

        # Published upcoming events count subquery (No N+1)
        events_count_subq = (
            select(func.count(Event.id))
            .where(
                and_(
                    Event.organization_id == Organization.id,
                    Event.status == EventStatus.PUBLISHED.value
                )
            )
            .scalar_subquery()
        )

        stmt = (
            select(
                Organization,
                City.name.label("city_name"),
                followers_subq.label("followers_count"),
                events_count_subq.label("events_count")
            )
            .outerjoin(City, Organization.city_id == City.id)
            .where(Organization.status == OrganizationStatus.ACTIVE.value)
        )

        if city_id:
            stmt = stmt.where(Organization.city_id == city_id)

        match_conditions = [
            Organization.name.ilike(term),
            Organization.description.ilike(term),
            Organization.category.ilike(term),
            Organization.address.ilike(term),
            City.name.ilike(term),
        ]
        if translit_term:
            t_term = f"%{translit_term}%"
            match_conditions.extend([
                Organization.name.ilike(t_term),
                Organization.description.ilike(t_term),
                Organization.category.ilike(t_term),
                City.name.ilike(t_term),
            ])

        stmt = stmt.where(or_(*match_conditions))
        stmt = stmt.order_by(Organization.is_verified.desc(), Organization.created_at.desc())

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).all()

        # User subscriptions if authenticated
        user_subscribed_org_ids: Set[str] = set()
        if current_user_id and rows:
            org_ids = [r[0].id for r in rows]
            sub_q = select(Subscription.organization_id).where(
                and_(Subscription.user_id == current_user_id, Subscription.organization_id.in_(org_ids))
            )
            sub_res = await session.execute(sub_q)
            user_subscribed_org_ids = set(sub_res.scalars().all())

        summaries: List[OrganizationSummary] = []
        for org, c_name, f_count, e_count in rows:
            summaries.append(
                OrganizationSummary(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    category=org.category,
                    city_id=org.city_id,
                    city_name=c_name,
                    address=org.address,
                    latitude=org.latitude,
                    longitude=org.longitude,
                    avatar_url=org.avatar_url,
                    status=org.status,
                    is_verified=org.is_verified,
                    followers_count=f_count or 0,
                    events_count=e_count or 0,
                    is_subscribed=org.id in user_subscribed_org_ids,
                    is_owner=bool(current_user_id and org.owner_user_id == current_user_id),
                    created_at=org.created_at
                )
            )

        return summaries, total

    @staticmethod
    async def search_venues(
        session: AsyncSession,
        query: str,
        city_id: Optional[str] = None,
        limit: int = 10,
        translit_term: Optional[str] = None
    ) -> Tuple[List[VenueSummary], int]:
        """
        Dynamically extracts and ranks physical venues from:
        1. Published events grouped by (venue_name, address, city_id)
        2. Active physical organizations (having an address or venue-type category)
        Eliminates duplicates and calculates upcoming event count without N+1.
        """
        clean_q = query.strip()
        term = f"%{clean_q}%"
        venues_map: Dict[str, VenueSummary] = {}

        # 1. Venues from published events
        event_match = [
            Event.venue_name.ilike(term),
            Event.address.ilike(term),
        ]
        if translit_term:
            t_term = f"%{translit_term}%"
            event_match.extend([
                Event.venue_name.ilike(t_term),
                Event.address.ilike(t_term),
            ])

        event_venue_stmt = (
            select(
                Event.venue_name,
                Event.address,
                Event.city_id,
                City.name.label("city_name"),
                Event.latitude,
                Event.longitude,
                Event.organization_id,
                Organization.name.label("org_name"),
                Organization.avatar_url.label("org_avatar"),
                func.count(Event.id).label("upcoming_events_count")
            )
            .join(City, Event.city_id == City.id)
            .outerjoin(Organization, Event.organization_id == Organization.id)
            .where(
                and_(
                    Event.status == EventStatus.PUBLISHED.value,
                    or_(*event_match)
                )
            )
        )

        if city_id:
            event_venue_stmt = event_venue_stmt.where(Event.city_id == city_id)

        event_venue_stmt = (
            event_venue_stmt
            .group_by(
                Event.venue_name,
                Event.address,
                Event.city_id,
                City.name,
                Event.latitude,
                Event.longitude,
                Event.organization_id,
                Organization.name,
                Organization.avatar_url
            )
            .order_by(func.count(Event.id).desc())
            .limit(limit)
        )

        event_venue_rows = (await session.execute(event_venue_stmt)).all()
        for v_name, v_addr, v_city_id, v_city_name, v_lat, v_lon, org_id, org_name, org_avatar, ev_count in event_venue_rows:
            key = f"{v_name.strip().lower()}::{v_city_id or ''}"
            venue_id = f"venue_{abs(hash(key)) % 10000000}"
            venues_map[key] = VenueSummary(
                id=venue_id,
                name=v_name,
                address=v_addr,
                city_id=v_city_id,
                city_name=v_city_name,
                latitude=v_lat,
                longitude=v_lon,
                organization_id=org_id,
                organization_name=org_name,
                organization_avatar_url=org_avatar,
                upcoming_events_count=ev_count or 0
            )

        # 2. Venues from physical organizations
        physical_categories = {
            "Кафе", "Ресторан", "Бар", "Клуб", "Концертная площадка",
            "Театр", "Спорт", "Культура"
        }
        org_venue_stmt = (
            select(
                Organization,
                City.name.label("city_name"),
                (
                    select(func.count(Event.id))
                    .where(
                        and_(
                            Event.organization_id == Organization.id,
                            Event.status == EventStatus.PUBLISHED.value
                        )
                    )
                    .scalar_subquery()
                ).label("upcoming_events_count")
            )
            .outerjoin(City, Organization.city_id == City.id)
            .where(
                and_(
                    Organization.status == OrganizationStatus.ACTIVE.value,
                    or_(
                        Organization.address.isnot(None),
                        Organization.category.in_(physical_categories)
                    )
                )
            )
        )

        if city_id:
            org_venue_stmt = org_venue_stmt.where(Organization.city_id == city_id)

        org_match = [
            Organization.name.ilike(term),
            Organization.address.ilike(term),
            Organization.category.ilike(term),
        ]
        if translit_term:
            t_term = f"%{translit_term}%"
            org_match.extend([
                Organization.name.ilike(t_term),
                Organization.address.ilike(t_term),
            ])

        org_venue_stmt = org_venue_stmt.where(or_(*org_match)).limit(limit)
        org_venue_rows = (await session.execute(org_venue_stmt)).all()

        for org, c_name, ev_count in org_venue_rows:
            key = f"{org.name.strip().lower()}::{org.city_id or ''}"
            if key in venues_map:
                # Merge: enrich with organization link if missing
                existing = venues_map[key]
                if not existing.organization_id:
                    existing.organization_id = org.id
                    existing.organization_name = org.name
                    existing.organization_avatar_url = org.avatar_url
            else:
                venues_map[key] = VenueSummary(
                    id=f"org_venue_{org.id}",
                    name=org.name,
                    address=org.address,
                    city_id=org.city_id,
                    city_name=c_name,
                    latitude=org.latitude,
                    longitude=org.longitude,
                    organization_id=org.id,
                    organization_name=org.name,
                    organization_avatar_url=org.avatar_url,
                    upcoming_events_count=ev_count or 0
                )

        venues_list = sorted(venues_map.values(), key=lambda v: v.upcoming_events_count, reverse=True)[:limit]
        return venues_list, len(venues_list)

    @classmethod
    async def unified_search(
        cls,
        session: AsyncSession,
        query: str,
        city_id: Optional[str] = None,
        category_id: Optional[str] = None,
        current_user_id: Optional[int] = None,
        limit: int = 15
    ) -> UnifiedDiscoveryResponse:
        """
        Executes unified search across Events, Organizations, and Venues.
        Returns single structured response.
        """
        clean_q = query.strip()
        if not clean_q:
            return UnifiedDiscoveryResponse(
                query="",
                city_id=city_id,
                events=[],
                organizations=[],
                venues=[],
                total_events=0,
                total_organizations=0,
                total_venues=0
            )

        translit_term = transliterate_latin_to_cyrillic(clean_q)

        # Detect if query explicitly names a city
        effective_city_id = city_id
        if not effective_city_id:
            check_q = clean_q.lower()
            city_res = await session.execute(
                select(City.id).where(
                    or_(
                        City.name.ilike(f"{check_q}%"),
                        City.id == check_q,
                        *([City.name.ilike(f"{translit_term}%")] if translit_term else [])
                    )
                ).limit(1)
            )
            detected_city_id = city_res.scalar_one_or_none()
            if detected_city_id:
                effective_city_id = detected_city_id

        # Query all three domains concurrently / sequentially in session
        events, total_events = await cls.search_events(
            session=session,
            query=clean_q,
            city_id=effective_city_id,
            category_id=category_id,
            current_user_id=current_user_id,
            limit=limit,
            translit_term=translit_term
        )

        organizations, total_orgs = await cls.search_organizations(
            session=session,
            query=clean_q,
            city_id=effective_city_id,
            current_user_id=current_user_id,
            limit=limit,
            translit_term=translit_term
        )

        venues, total_venues = await cls.search_venues(
            session=session,
            query=clean_q,
            city_id=effective_city_id,
            limit=limit,
            translit_term=translit_term
        )

        return UnifiedDiscoveryResponse(
            query=clean_q,
            city_id=effective_city_id,
            events=events,
            organizations=organizations,
            venues=venues,
            total_events=total_events,
            total_organizations=total_orgs,
            total_venues=total_venues
        )


discovery_service = DiscoveryService()
