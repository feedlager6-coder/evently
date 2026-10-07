from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas.event import EventSummary, EventResponse
from app.schemas.moderation import RejectRequest
from app.schemas.entitlement import OrganizerEntitlementsResponse, SetPlanRequest
from app.api.deps import require_admin
from app.services.moderation_service import (
    get_admin_events,
    publish_event,
    reject_event,
    cancel_event
)
from app.services.event_service import get_event_details, EventNotFoundError
from app.services.entitlement_service import EntitlementService
from app.services import notification_service

router = APIRouter(prefix="/admin", tags=["Admin Moderation"])


@router.get("/events", response_model=List[EventSummary])
async def list_moderation_queue(
    status: Optional[str] = Query(None, pattern="^(pending|published|rejected|cancelled|all)$"),
    status_filter: Optional[str] = Query(None, pattern="^(pending|published|rejected|cancelled|all)$"),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Admin moderation queue. Lists events filtered by status (default 'pending').
    Accepts both ?status= and ?status_filter= parameters for seamless frontend compatibility.
    Protected by admin RBAC check.
    """
    raw_status = status or status_filter or "pending"
    effective_status = None if raw_status == "all" else raw_status
    return await get_admin_events(session, status_filter=effective_status)


@router.post("/events/{event_id}/publish", response_model=EventResponse)
async def admin_publish_event(
    event_id: str,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Approves and publishes an event, making it immediately visible in public discovery.
    Triggers asynchronous notification to subscribers if event belongs to an organization.
    """
    try:
        event = await publish_event(session, event_id)
        if event.organization_id:
            background_tasks.add_task(notification_service.notify_organization_subscribers, event.id)
        return await get_event_details(session, event_id)
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/events/{event_id}/reject", response_model=EventResponse)
async def admin_reject_event(
    event_id: str,
    payload: Optional[RejectRequest] = None,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Rejects an event submission with an optional explanation.
    """
    reason = payload.reason if payload else None
    try:
        await reject_event(session, event_id, reason=reason)
        return await get_event_details(session, event_id)
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/events/{event_id}/cancel", response_model=EventResponse)
async def admin_cancel_event(
    event_id: str,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Cancels a previously published event, removing it from public discovery.
    """
    try:
        await cancel_event(session, event_id)
        return await get_event_details(session, event_id)
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


from app.models.organization import Organization, OrganizationStatus
from app.models.organization_plan import OrganizationPlan
from app.schemas.entitlement import (
    OrganizerEntitlementsResponse,
    SetPlanRequest,
    AdminOrganizationSummary,
)


@router.get("/organizations", response_model=List[AdminOrganizationSummary])
async def admin_list_organizations(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists all active organizations with their current plan for admin inspection and testing.
    """
    stmt = (
        select(Organization, OrganizationPlan.plan, OrganizationPlan.status)
        .outerjoin(OrganizationPlan, Organization.id == OrganizationPlan.organization_id)
        .where(Organization.status != OrganizationStatus.DELETED.value)
        .order_by(Organization.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    results = []
    for org, plan, plan_status in rows:
        results.append(
            AdminOrganizationSummary(
                id=org.id,
                name=org.name,
                slug=org.slug,
                category=org.category,
                city_id=org.city_id,
                owner_user_id=org.owner_user_id,
                status=org.status,
                plan=plan or "free",
                plan_status=plan_status or "active",
                created_at=org.created_at,
            )
        )
    return results


@router.get("/organizations/{org_id}/entitlements", response_model=OrganizerEntitlementsResponse)
async def admin_get_organization_entitlements(
    org_id: str,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Admin/Dev visibility endpoint to inspect current plan, capabilities, and limits for an organization.
    """
    org = await session.get(Organization, org_id)
    if not org or org.status == OrganizationStatus.DELETED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
    return await EntitlementService.get_entitlements(session, org_id, org_name=org.name)


@router.post("/organizations/{org_id}/plan", response_model=OrganizerEntitlementsResponse)
async def admin_set_organization_plan(
    org_id: str,
    payload: SetPlanRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Admin/Dev capability to switch an organization's plan (e.g. Free <-> Pro) for testing and dev verification.
    """
    org = await session.get(Organization, org_id)
    if not org or org.status == OrganizationStatus.DELETED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")

    expires_at = None
    if payload.expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    await EntitlementService.set_organization_plan(
        session=session,
        organization_id=org_id,
        plan=payload.plan,
        status_val=payload.status or "active",
        expires_at=expires_at
    )
    return await EntitlementService.get_entitlements(session, org_id, org_name=org.name)


@router.post("/reminders/process")
async def admin_process_reminders(
    force_all_daytime: bool = False,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Manually triggers processing of due event reminders.
    Safe, idempotent, and daytime-aware (or forced for testing).
    """
    from app.services.reminder_service import process_due_reminders
    report = await process_due_reminders(session, force_all_daytime=force_all_daytime)
    return {"status": "ok", "report": report}


@router.get("/reminders/diagnostics")
async def admin_get_reminder_diagnostics(
    admin: User = Depends(require_admin),
):
    """
    Returns diagnostics on periodic reminders: last run, lifetime stats, and window rules.
    """
    from app.services.reminder_service import get_reminder_diagnostics
    return get_reminder_diagnostics()



