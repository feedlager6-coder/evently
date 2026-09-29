import re
import uuid
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.organization import Organization, OrganizationStatus
from app.models.subscription import Subscription
from app.models.event import Event, EventStatus
from app.models.city import City
from app.models.user import User
from app.models.attendee import EventAttendee
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationSummary,
    OrganizationResponse
)
from app.schemas.subscription import (
    SubscriptionStatusResponse,
    UserSubscriptionItem
)
from app.schemas.event import EventSummary

logger = logging.getLogger("evently.organizations")


CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def slugify(text: str) -> str:
    """Generates clean, URL-safe slug supporting Russian Cyrillic and English."""
    text = text.lower().strip()
    result = []
    for char in text:
        if char in CYRILLIC_TO_LATIN:
            result.append(CYRILLIC_TO_LATIN[char])
        elif char.isalnum():
            result.append(char)
        elif char in (' ', '-', '_', '.'):
            result.append('-')
    raw_slug = ''.join(result)
    cleaned = re.sub(r'-+', '-', raw_slug).strip('-')
    return cleaned[:80] or "org"


async def generate_unique_slug(session: AsyncSession, name: str) -> str:
    """Generates a unique slug for a new organization."""
    base_slug = slugify(name)
    stmt = select(func.count(Organization.id)).where(Organization.slug == base_slug)
    count = (await session.execute(stmt)).scalar() or 0
    if count == 0:
        return base_slug

    suffix = uuid.uuid4().hex[:6]
    return f"{base_slug}-{suffix}"


async def get_followers_count(session: AsyncSession, org_id: str) -> int:
    """Returns total subscriber count for an organization."""
    stmt = select(func.count(Subscription.id)).where(Subscription.organization_id == org_id)
    return (await session.execute(stmt)).scalar() or 0


async def check_is_subscribed(session: AsyncSession, org_id: str, user_id: Optional[int]) -> bool:
    """Checks whether user is subscribed to the organization."""
    if not user_id:
        return False
    stmt = select(Subscription.id).where(
        and_(Subscription.organization_id == org_id, Subscription.user_id == user_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def create_organization(
    session: AsyncSession,
    data: OrganizationCreate,
    owner_user_id: int
) -> OrganizationResponse:
    """Creates a new organization owned by the authenticated user."""
    slug = await generate_unique_slug(session, data.name)

    # Validate city if provided
    city_name = None
    if data.city_id:
        city_res = await session.execute(select(City).where(City.id == data.city_id))
        city = city_res.scalar_one_or_none()
        if city:
            city_name = city.name

    org = Organization(
        owner_user_id=owner_user_id,
        name=data.name.strip(),
        slug=slug,
        description=data.description.strip() if data.description else None,
        category=data.category.strip(),
        city_id=data.city_id,
        address=data.address.strip() if data.address else None,
        latitude=data.latitude,
        longitude=data.longitude,
        avatar_url=data.avatar_url,
        website=data.website.strip() if data.website else None,
        social_link=data.social_link.strip() if data.social_link else None,
        status=OrganizationStatus.ACTIVE.value,
        is_verified=False
    )
    session.add(org)
    await session.commit()
    await session.refresh(org)

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        category=org.category,
        description=org.description,
        city_id=org.city_id,
        city_name=city_name,
        address=org.address,
        latitude=org.latitude,
        longitude=org.longitude,
        avatar_url=org.avatar_url,
        website=org.website,
        social_link=org.social_link,
        status=org.status,
        is_verified=org.is_verified,
        followers_count=0,
        is_subscribed=False,
        is_owner=True,
        owner_user_id=org.owner_user_id,
        created_at=org.created_at,
        updated_at=org.updated_at
    )


async def get_organization_by_id_or_slug(
    session: AsyncSession,
    org_id_or_slug: str,
    current_user_id: Optional[int] = None
) -> OrganizationResponse:
    """Fetches public organization profile with follower count and subscriber status."""
    stmt = (
        select(Organization, City.name.label("city_name"))
        .outerjoin(City, Organization.city_id == City.id)
        .where(
            or_(Organization.id == org_id_or_slug, Organization.slug == org_id_or_slug)
        )
    )
    res = await session.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Организация '{org_id_or_slug}' не найдена"
        )

    org, city_name = row
    followers_count = await get_followers_count(session, org.id)
    is_sub = await check_is_subscribed(session, org.id, current_user_id)
    is_owner = bool(current_user_id and org.owner_user_id == current_user_id)

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        category=org.category,
        description=org.description,
        city_id=org.city_id,
        city_name=city_name,
        address=org.address,
        latitude=org.latitude,
        longitude=org.longitude,
        avatar_url=org.avatar_url,
        website=org.website,
        social_link=org.social_link,
        status=org.status,
        is_verified=org.is_verified,
        followers_count=followers_count,
        is_subscribed=is_sub,
        is_owner=is_owner,
        owner_user_id=org.owner_user_id,
        created_at=org.created_at,
        updated_at=org.updated_at
    )


async def update_organization(
    session: AsyncSession,
    org_id: str,
    data: OrganizationUpdate,
    current_user_id: int
) -> OrganizationResponse:
    """Updates organization profile. Strictly verifies that current user is the owner."""
    res = await session.execute(select(Organization).where(Organization.id == org_id))
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Организация '{org_id}' не найдена"
        )

    if org.owner_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не можете редактировать чужую организацию"
        )

    if data.name is not None and data.name.strip():
        org.name = data.name.strip()
    if data.category is not None and data.category.strip():
        org.category = data.category.strip()
    if data.description is not None:
        org.description = data.description.strip() if data.description else None
    if data.city_id is not None:
        org.city_id = data.city_id or None
    if data.address is not None:
        org.address = data.address.strip() if data.address else None
    if data.latitude is not None:
        org.latitude = data.latitude
    if data.longitude is not None:
        org.longitude = data.longitude
    if data.avatar_url is not None:
        org.avatar_url = data.avatar_url
    if data.website is not None:
        org.website = data.website.strip() if data.website else None
    if data.social_link is not None:
        org.social_link = data.social_link.strip() if data.social_link else None
    if data.status is not None:
        org.status = data.status

    org.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(org)

    return await get_organization_by_id_or_slug(session, org.id, current_user_id)


async def list_user_organizations(
    session: AsyncSession,
    user_id: int
) -> List[OrganizationSummary]:
    """Lists organizations owned by the given user."""
    stmt = (
        select(Organization, City.name.label("city_name"))
        .outerjoin(City, Organization.city_id == City.id)
        .where(Organization.owner_user_id == user_id)
        .order_by(Organization.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    summaries = []
    for org, city_name in rows:
        followers_count = await get_followers_count(session, org.id)
        summaries.append(
            OrganizationSummary(
                id=org.id,
                name=org.name,
                slug=org.slug,
                category=org.category,
                city_id=org.city_id,
                city_name=city_name,
                address=org.address,
                latitude=org.latitude,
                longitude=org.longitude,
                avatar_url=org.avatar_url,
                status=org.status,
                is_verified=org.is_verified,
                followers_count=followers_count,
                is_subscribed=False,
                is_owner=True,
                created_at=org.created_at
            )
        )
    return summaries


async def list_organization_events(
    session: AsyncSession,
    org_id: str,
    current_user_id: Optional[int] = None
) -> List[EventSummary]:
    """
    Lists events for an organization.
    Public visitors see only published events.
    The owner can see both published and pending events.
    """
    # Check if viewer is owner
    org_res = await session.execute(select(Organization).where(Organization.id == org_id))
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Организация '{org_id}' не найдена"
        )

    is_owner = bool(current_user_id and org.owner_user_id == current_user_id)

    attendee_count_subq = (
        select(func.count(EventAttendee.user_id))
        .where(EventAttendee.event_id == Event.id)
        .scalar_subquery()
    )

    query = (
        select(
            Event,
            City.name.label("city_name"),
            attendee_count_subq.label("attendee_count")
        )
        .outerjoin(City, Event.city_id == City.id)
        .where(Event.organization_id == org_id)
    )

    if not is_owner:
        query = query.where(Event.status == EventStatus.PUBLISHED.value)
    else:
        query = query.where(Event.status.in_([EventStatus.PUBLISHED.value, EventStatus.PENDING.value]))

    query = query.order_by(Event.start_at.asc())

    rows = (await session.execute(query)).all()

    # User attendances
    attending_event_ids = set()
    if current_user_id:
        att_stmt = select(EventAttendee.event_id).where(EventAttendee.user_id == current_user_id)
        attending_event_ids = set((await session.execute(att_stmt)).scalars().all())

    summaries = []
    for ev, c_name, att_count in rows:
        summaries.append(
            EventSummary(
                id=ev.id,
                title=ev.title,
                cover_image_url=ev.cover_image_url,
                category_id=ev.category_id,
                city_id=ev.city_id,
                city_name=c_name,
                start_at=ev.start_at,
                venue_name=ev.venue_name,
                latitude=ev.latitude,
                longitude=ev.longitude,
                price_amount=ev.price_amount,
                price_currency=ev.price_currency,
                is_free=(ev.price_amount is None or ev.price_amount == 0),
                attendee_count=att_count or 0,
                status=ev.status,
                is_attending=(ev.id in attending_event_ids),
                organization_id=org.id,
                organization_name=org.name,
                organization_category=org.category,
                organization_avatar_url=org.avatar_url
            )
        )
    return summaries


async def subscribe_organization(
    session: AsyncSession,
    org_id: str,
    user_id: int
) -> SubscriptionStatusResponse:
    """
    Idempotent subscription creation.
    Repeated calls safely return existing subscription status without duplicates.
    """
    org_res = await session.execute(select(Organization).where(Organization.id == org_id))
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Организация '{org_id}' не найдена"
        )

    # Check if already subscribed
    stmt = select(Subscription).where(
        and_(Subscription.organization_id == org_id, Subscription.user_id == user_id)
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if not existing:
        sub = Subscription(user_id=user_id, organization_id=org_id, notifications_enabled=True)
        session.add(sub)
        await session.commit()

    followers_count = await get_followers_count(session, org_id)
    return SubscriptionStatusResponse(
        is_subscribed=True,
        followers_count=followers_count,
        message="Вы успешно подписались на организацию"
    )


async def unsubscribe_organization(
    session: AsyncSession,
    org_id: str,
    user_id: int
) -> SubscriptionStatusResponse:
    """
    Idempotent unsubscribe. Safe even if subscription was already deleted.
    """
    org_res = await session.execute(select(Organization).where(Organization.id == org_id))
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Организация '{org_id}' не найдена"
        )

    del_stmt = delete(Subscription).where(
        and_(Subscription.organization_id == org_id, Subscription.user_id == user_id)
    )
    await session.execute(del_stmt)
    await session.commit()

    followers_count = await get_followers_count(session, org_id)
    return SubscriptionStatusResponse(
        is_subscribed=False,
        followers_count=followers_count,
        message="Вы отписались от организации"
    )


async def list_user_subscriptions(
    session: AsyncSession,
    user_id: int
) -> List[UserSubscriptionItem]:
    """Lists all organizations the user is currently subscribed to."""
    stmt = (
        select(Subscription, Organization, City.name.label("city_name"))
        .join(Organization, Subscription.organization_id == Organization.id)
        .outerjoin(City, Organization.city_id == City.id)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    items = []
    for sub, org, city_name in rows:
        followers_count = await get_followers_count(session, org.id)
        summary = OrganizationSummary(
            id=org.id,
            name=org.name,
            slug=org.slug,
            category=org.category,
            city_id=org.city_id,
            city_name=city_name,
            address=org.address,
            latitude=org.latitude,
            longitude=org.longitude,
            avatar_url=org.avatar_url,
            status=org.status,
            is_verified=org.is_verified,
            followers_count=followers_count,
            is_subscribed=True,
            is_owner=(org.owner_user_id == user_id),
            created_at=org.created_at
        )
        items.append(
            UserSubscriptionItem(
                id=sub.id,
                organization=summary,
                created_at=sub.created_at
            )
        )
    return items
