import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, case, union

from app.models.organization import Organization, OrganizationStatus
from app.models.subscription import Subscription
from app.models.event import Event
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.models.view import EventView
from app.models.broadcast import Broadcast, BroadcastRecipient
from app.schemas.insights import (
    AudienceGrowthMetrics,
    EventPerformanceTotals,
    BroadcastPerformanceTotals,
    ViewSourceMetric,
    OrganizerInsightsResponse,
)

logger = logging.getLogger("evently.insights")

SOURCE_LABELS: Dict[str, str] = {
    "discovery": "Афиша",
    "broadcast": "Рассылки",
    "deep_link": "Прямая ссылка",
    "inline": "Поделились",
    "personal": "Мои события",
    "organizer": "Кабинет",
    "unknown": "Другое",
}


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _generate_fact_sentence(
    audience: AudienceGrowthMetrics,
    events: EventPerformanceTotals,
    broadcasts: BroadcastPerformanceTotals,
) -> str:
    if events.total_events == 0 and audience.total_subscribers == 0:
        return "Создайте первое событие или организацию, чтобы начать привлекать аудиторию."
    
    if broadcasts.total_attributed_rsvp > 0:
        return (
            f"Рассылки принесли {broadcasts.total_opened} переходов и "
            f"{broadcasts.total_attributed_rsvp} подтвержденных гостей на ваши события"
        )
    
    if broadcasts.total_opened > 0:
        return f"Рассылки принесли {broadcasts.total_opened} переходов на страницы ваших событий"
    
    if audience.new_subscribers_7d > 0:
        return f"+{audience.new_subscribers_7d} новых подписчиков за последние 7 дней"
    
    if events.total_rsvps > 0:
        return f"{events.total_rsvps} гостей подтвердили участие в ваших событиях"
    
    if events.total_views > 0:
        return f"Ваши события просмотрели {events.total_views} раз"
    
    return "События опубликованы и готовы к привлечению гостей"


async def get_organizer_insights(
    session: AsyncSession,
    organizer_user_id: int,
) -> OrganizerInsightsResponse:
    """
    Computes verified, non-faked Organizer Insights for the authenticated user.
    Aggregates audience growth, event performance totals, broadcast attribution totals,
    and discovery view sources with strict metric separation.
    """
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    # 1. Fetch owned organizations
    org_res = await session.execute(
        select(Organization.id).where(
            Organization.owner_user_id == organizer_user_id,
            Organization.status != OrganizationStatus.DELETED.value
        )
    )
    owned_org_ids = [row[0] for row in org_res.all()]

    # 2. Fetch owned events
    if owned_org_ids:
        event_query = select(Event).where(
            or_(
                Event.organizer_user_id == organizer_user_id,
                Event.organization_id.in_(owned_org_ids),
            )
        )
    else:
        event_query = select(Event).where(Event.organizer_user_id == organizer_user_id)

    event_res = await session.execute(event_query)
    all_events = event_res.scalars().all()
    all_event_ids = [e.id for e in all_events]

    # 3. Audience metrics
    total_subs = 0
    new_subs_7d = 0
    new_subs_30d = 0

    if owned_org_ids:
        sub_total_res = await session.execute(
            select(func.count(Subscription.id)).where(Subscription.organization_id.in_(owned_org_ids))
        )
        total_subs = sub_total_res.scalar() or 0

        sub_7d_res = await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.organization_id.in_(owned_org_ids),
                Subscription.created_at >= d7,
            )
        )
        new_subs_7d = sub_7d_res.scalar() or 0

        sub_30d_res = await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.organization_id.in_(owned_org_ids),
                Subscription.created_at >= d30,
            )
        )
        new_subs_30d = sub_30d_res.scalar() or 0

    # Unique engaged reach
    user_id_queries = []
    if owned_org_ids:
        user_id_queries.append(
            select(Subscription.user_id.label("uid")).where(Subscription.organization_id.in_(owned_org_ids))
        )
    if all_event_ids:
        user_id_queries.append(
            select(EventAttendee.user_id.label("uid")).where(EventAttendee.event_id.in_(all_event_ids))
        )
        user_id_queries.append(
            select(EventInterest.user_id.label("uid")).where(EventInterest.event_id.in_(all_event_ids))
        )

    if user_id_queries:
        union_q = union(*user_id_queries).subquery()
        engaged_count_q = select(func.count(union_q.c.uid))
        total_unique_engaged = (await session.execute(engaged_count_q)).scalar() or 0
    else:
        total_unique_engaged = 0

    audience_metrics = AudienceGrowthMetrics(
        total_subscribers=total_subs,
        new_subscribers_7d=new_subs_7d,
        new_subscribers_30d=new_subs_30d,
        total_unique_engaged=total_unique_engaged,
    )

    # 4. Events performance totals
    total_events = len(all_events)
    upcoming_count = sum(1 for e in all_events if e.start_at and to_utc(e.start_at) >= now and e.status != "cancelled")
    past_count = sum(1 for e in all_events if e.start_at and (to_utc(e.start_at) < now or e.status == "cancelled"))

    total_views = 0
    total_interest = 0
    total_rsvps = 0

    if all_event_ids:
        v_res = await session.execute(
            select(func.count(EventView.id)).where(EventView.event_id.in_(all_event_ids))
        )
        total_views = v_res.scalar() or 0

        int_res = await session.execute(
            select(func.count(EventInterest.id)).where(EventInterest.event_id.in_(all_event_ids))
        )
        total_interest = int_res.scalar() or 0

        att_res = await session.execute(
            select(func.count(EventAttendee.user_id)).where(EventAttendee.event_id.in_(all_event_ids))
        )
        total_rsvps = att_res.scalar() or 0

    events_metrics = EventPerformanceTotals(
        total_events=total_events,
        upcoming_events_count=upcoming_count,
        past_events_count=past_count,
        total_views=total_views,
        total_interest=total_interest,
        total_rsvps=total_rsvps,
    )

    # 5. Broadcasts performance totals
    if owned_org_ids:
        bcast_stmt = select(Broadcast).where(
            or_(
                Broadcast.created_by_user_id == organizer_user_id,
                Broadcast.organization_id.in_(owned_org_ids),
            )
        )
    else:
        bcast_stmt = select(Broadcast).where(Broadcast.created_by_user_id == organizer_user_id)

    bcast_res = await session.execute(bcast_stmt)
    all_broadcasts = bcast_res.scalars().all()
    bcast_ids = [b.id for b in all_broadcasts]

    total_broadcasts = len(all_broadcasts)
    total_delivered = sum(b.delivered_count or 0 for b in all_broadcasts)
    total_opened = 0
    total_attr_interest = 0
    total_attr_rsvp = 0

    if bcast_ids:
        rec_stmt = (
            select(
                func.count(case((BroadcastRecipient.opened_at.isnot(None), 1))).label("opened_count"),
                func.count(case((BroadcastRecipient.attributed_interest_at.isnot(None), 1))).label("interest_count"),
                func.count(case((BroadcastRecipient.attributed_rsvp_at.isnot(None), 1))).label("rsvp_count"),
            )
            .where(BroadcastRecipient.broadcast_id.in_(bcast_ids))
        )
        rec_row = (await session.execute(rec_stmt)).first()
        if rec_row:
            total_opened = rec_row.opened_count or 0
            total_attr_interest = rec_row.interest_count or 0
            total_attr_rsvp = rec_row.rsvp_count or 0

    open_rate = min(round((total_opened / total_delivered) * 100, 1), 100.0) if total_delivered > 0 else 0.0
    interest_conv = min(round((total_attr_interest / total_delivered) * 100, 1), 100.0) if total_delivered > 0 else 0.0
    rsvp_conv = min(round((total_attr_rsvp / total_delivered) * 100, 1), 100.0) if total_delivered > 0 else 0.0

    broadcasts_metrics = BroadcastPerformanceTotals(
        total_broadcasts=total_broadcasts,
        total_delivered=total_delivered,
        total_opened=total_opened,
        total_attributed_interest=total_attr_interest,
        total_attributed_rsvp=total_attr_rsvp,
        overall_open_rate=open_rate,
        overall_interest_conversion=interest_conv,
        overall_rsvp_conversion=rsvp_conv,
    )

    # 6. Views sources breakdown
    source_metrics: List[ViewSourceMetric] = []
    if all_event_ids:
        source_stmt = (
            select(
                EventView.source,
                func.count(EventView.id).label("cnt")
            )
            .where(EventView.event_id.in_(all_event_ids))
            .group_by(EventView.source)
            .order_by(func.count(EventView.id).desc())
        )
        source_rows = (await session.execute(source_stmt)).all()

        for src, cnt in source_rows:
            clean_src = src or "unknown"
            label = SOURCE_LABELS.get(clean_src, "Другое")
            pct = round((cnt / total_views) * 100, 1) if total_views > 0 else 0.0
            source_metrics.append(
                ViewSourceMetric(
                    source=clean_src,
                    label=label,
                    views_count=cnt,
                    percentage=pct,
                )
            )

    # 7. Fact sentence & has_data
    has_data = bool(total_events > 0 or total_subs > 0 or total_broadcasts > 0)
    fact_sentence = _generate_fact_sentence(audience_metrics, events_metrics, broadcasts_metrics)

    return OrganizerInsightsResponse(
        audience=audience_metrics,
        events=events_metrics,
        broadcasts=broadcasts_metrics,
        sources=source_metrics,
        fact_sentence=fact_sentence,
        has_data=has_data,
    )
