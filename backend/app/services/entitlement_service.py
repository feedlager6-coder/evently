import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.config import settings
from app.models.organization_plan import OrganizationPlan, PlanType, PlanStatus
from app.models.organization import Organization, OrganizationStatus
from app.models.broadcast import Broadcast, BroadcastStatus, BroadcastType
from app.schemas.entitlement import (
    CapabilityStatus,
    CapabilityInfo,
    EntitlementLimits,
    OrganizerEntitlementsResponse,
)

logger = logging.getLogger("evently.entitlements")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# Central Capability Definition Registry
# Each capability declares its title, description, whether it requires Pro, and its status per plan.
CAPABILITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "broadcasts_extended": {
        "title": "Рассылки аудитории",
        "description": "Отправка анонсов и сообщений подписчикам организации прямо в Telegram",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.LOCKED,
            PlanType.PRO.value: CapabilityStatus.AVAILABLE,
        },
    },
    "audience_advanced": {
        "title": "Глубокая аналитика аудитории",
        "description": "Динамика роста базы за 30/90 дней, повторные посещения и источники новых подписчиков",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.LOCKED,
            PlanType.PRO.value: CapabilityStatus.AVAILABLE,
        },
    },
    "analytics_advanced": {
        "title": "Расширенная аналитика событий",
        "description": "Пошаговая воронка конверсии (просмотр → интерес → RSVP) и экспорт отчетов",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.LOCKED,
            PlanType.PRO.value: CapabilityStatus.AVAILABLE,
        },
    },
    "reminders": {
        "title": "Авто-напоминания о событиях",
        "description": "Автоматические сообщения зарегистрированным гостям за 24 часа и 2 часа до начала",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.COMING_SOON,
            PlanType.PRO.value: CapabilityStatus.COMING_SOON,
        },
    },
    "audience_segments": {
        "title": "Сегментация аудитории",
        "description": "Таргетинг по частым гостям, новым подписчикам и категориям посещенных событий",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.COMING_SOON,
            PlanType.PRO.value: CapabilityStatus.COMING_SOON,
        },
    },
    "export": {
        "title": "Экспорт списков и CRM",
        "description": "Выгрузка списков гостей и подписчиков в формате CSV/XLSX для интеграции с CRM",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.COMING_SOON,
            PlanType.PRO.value: CapabilityStatus.COMING_SOON,
        },
    },
    "organization_verification": {
        "title": "Верификация организации",
        "description": "Синяя галочка подтвержденной площадки и статус проверенного организатора",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.COMING_SOON,
            PlanType.PRO.value: CapabilityStatus.COMING_SOON,
        },
    },
    "priority_placement": {
        "title": "Приоритетное размещение",
        "description": "Выделенное размещение в каталоге площадок города и еженедельных дайджестах",
        "is_pro_feature": True,
        "plans": {
            PlanType.FREE.value: CapabilityStatus.COMING_SOON,
            PlanType.PRO.value: CapabilityStatus.COMING_SOON,
        },
    },
}


class EntitlementService:
    """
    Centralized Entitlement & Capability Engine for Ivently.
    Source of truth for plan resolution, capability checks, and feature enforcement.
    Strictly isolated per Organization.
    """

    @classmethod
    async def get_organization_plan(
        cls,
        session: AsyncSession,
        organization_id: str
    ) -> Tuple[str, str, Optional[datetime], Optional[datetime]]:
        """
        Resolves the effective plan for an organization.
        Returns (effective_plan, status, starts_at, expires_at).
        Gracefully defaults to (FREE, ACTIVE, None, None) if no record exists or if expired.
        """
        stmt = select(OrganizationPlan).where(OrganizationPlan.organization_id == organization_id)
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            return PlanType.FREE.value, PlanStatus.ACTIVE.value, None, None

        now = utc_now()
        # Check expiration
        expires_at_utc = ensure_utc(record.expires_at)
        if expires_at_utc and expires_at_utc < now:
            return PlanType.FREE.value, PlanStatus.EXPIRED.value, record.starts_at, record.expires_at

        # Check explicit cancellation or inactive status
        if record.status != PlanStatus.ACTIVE.value:
            return PlanType.FREE.value, record.status, record.starts_at, record.expires_at

        # Active plan
        return record.plan, record.status, record.starts_at, record.expires_at

    @classmethod
    async def get_monthly_broadcast_usage(
        cls,
        session: AsyncSession,
        organization_id: str
    ) -> int:
        """
        Returns number of active/queued/completed marketing broadcasts sent by this organization
        in the current calendar month (from 1st of month 00:00:00 UTC).
        Transactional broadcasts (event updates), failed broadcasts (0 sent), cancelled,
        and other organizations' broadcasts do NOT count toward this marketing quota.
        """
        now = utc_now()
        start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)

        stmt = select(func.count(Broadcast.id)).where(
            Broadcast.organization_id == organization_id,
            Broadcast.created_at >= start_of_month,
            Broadcast.broadcast_type == BroadcastType.MARKETING.value,
            Broadcast.status.in_([
                BroadcastStatus.COMPLETED.value,
                BroadcastStatus.PROCESSING.value,
                BroadcastStatus.QUEUED.value,
                BroadcastStatus.PARTIALLY_FAILED.value
            ]),
            or_(
                Broadcast.status.in_([BroadcastStatus.QUEUED.value, BroadcastStatus.PROCESSING.value]),
                Broadcast.sent_count > 0
            )
        )
        return (await session.execute(stmt)).scalar() or 0

    @classmethod
    async def get_entitlements(
        cls,
        session: AsyncSession,
        organization_id: str,
        org_name: Optional[str] = None
    ) -> OrganizerEntitlementsResponse:
        """
        Returns complete, structured entitlements payload for frontend capability awareness.
        """
        plan, plan_status, starts_at, expires_at = await cls.get_organization_plan(session, organization_id)
        broadcast_usage = await cls.get_monthly_broadcast_usage(session, organization_id)

        monthly_limit = (
            settings.PRO_BROADCASTS_PER_MONTH
            if plan == PlanType.PRO.value
            else settings.FREE_BROADCASTS_PER_MONTH
        )
        remaining = max(0, monthly_limit - broadcast_usage)

        capabilities_map: Dict[str, CapabilityInfo] = {}
        for key, defn in CAPABILITY_REGISTRY.items():
            cap_status = defn["plans"].get(plan, CapabilityStatus.LOCKED)
            capabilities_map[key] = CapabilityInfo(
                key=key,
                title=defn["title"],
                description=defn["description"],
                status=cap_status,
                is_pro_feature=defn["is_pro_feature"],
                limit=monthly_limit if key == "broadcasts_extended" else None,
            )

        return OrganizerEntitlementsResponse(
            organization_id=organization_id,
            organization_name=org_name,
            plan=plan,
            status=plan_status,
            starts_at=starts_at,
            expires_at=expires_at,
            capabilities=capabilities_map,
            limits=EntitlementLimits(
                broadcasts_per_month=monthly_limit,
                broadcasts_used_this_month=broadcast_usage,
                broadcasts_remaining=remaining,
            ),
        )

    @classmethod
    async def check_capability(
        cls,
        session: AsyncSession,
        organization_id: str,
        capability_key: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Checks whether organization is entitled to use capability_key.
        Returns (is_allowed, reason, required_plan).
        """
        if capability_key not in CAPABILITY_REGISTRY:
            return False, f"Неизвестная возможность '{capability_key}'", None

        defn = CAPABILITY_REGISTRY[capability_key]
        plan, plan_status, _, _ = await cls.get_organization_plan(session, organization_id)
        cap_status = defn["plans"].get(plan, CapabilityStatus.LOCKED)

        if cap_status == CapabilityStatus.AVAILABLE:
            return True, "Доступно", None
        elif cap_status == CapabilityStatus.COMING_SOON:
            return False, f"Возможность «{defn['title']}» находится в разработке", None
        else:
            return False, f"Возможность «{defn['title']}» доступна в тарифе Pro", PlanType.PRO.value

    @classmethod
    async def require_entitlement(
        cls,
        session: AsyncSession,
        organization_id: str,
        capability_key: str
    ) -> None:
        """
        Central enforcement gate: verifies entitlement and raises HTTP 403 Forbidden
        with structured error detail if the organization lacks the required entitlement.
        """
        allowed, reason, required_plan = await cls.check_capability(session, organization_id, capability_key)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": reason,
                    "code": "ENTITLEMENT_REQUIRED",
                    "capability": capability_key,
                    "required_plan": required_plan,
                }
            )

    @classmethod
    async def enforce_broadcast_capacity(
        cls,
        session: AsyncSession,
        organization_id: str,
        broadcast_type: Optional[str] = None,
    ) -> None:
        """
        Enforces broadcast monthly quota per organization.
        Free tier organizations are entitled to FREE_BROADCASTS_PER_MONTH marketing broadcasts.
        Operational event updates (transactional) do not consume the monthly quota.
        Exceeding the quota triggers require_entitlement for 'broadcasts_extended'.
        """
        # Transactional messages (event changes, reschedules, cancellations) are operational and exempt
        if broadcast_type == BroadcastType.TRANSACTIONAL.value:
            return

        plan, plan_status, _, _ = await cls.get_organization_plan(session, organization_id)
        if plan != PlanType.PRO.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Для отправки рассылок требуется тариф Pro.",
                    "code": "ENTITLEMENT_REQUIRED",
                    "capability": "broadcasts_extended",
                    "required_plan": PlanType.PRO.value,
                }
            )

        used = await cls.get_monthly_broadcast_usage(session, organization_id)
        limit = settings.PRO_BROADCASTS_PER_MONTH

        if used >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": f"Достигнут лимит анонсов для тарифа Pro ({limit} в месяц).",
                    "code": "LIMIT_EXCEEDED",
                    "capability": "broadcasts_extended",
                    "used": used,
                    "limit": limit,
                }
            )

    @classmethod
    async def set_organization_plan(
        cls,
        session: AsyncSession,
        organization_id: str,
        plan: str,
        status_val: str = PlanStatus.ACTIVE.value,
        expires_at: Optional[datetime] = None
    ) -> OrganizationPlan:
        """
        Upserts OrganizationPlan record for an organization (used in testing, admin, and dev tooling).
        """
        stmt = select(OrganizationPlan).where(OrganizationPlan.organization_id == organization_id)
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()

        now = utc_now()
        if record:
            record.plan = plan
            record.status = status_val
            record.expires_at = expires_at
            record.updated_at = now
        else:
            record = OrganizationPlan(
                organization_id=organization_id,
                plan=plan,
                status=status_val,
                starts_at=now,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            session.add(record)

        await session.commit()
        await session.refresh(record)
        logger.info(
            "Organization %s plan set to %s (status=%s, expires_at=%s)",
            organization_id, plan, status_val, expires_at
        )
        return record
