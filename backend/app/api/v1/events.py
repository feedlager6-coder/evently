import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.event import EventListResponse, EventResponse, EventCreate
from app.schemas.rsvp import RSVPResponse
from app.schemas.interest import EventInterestResponse
from app.api.deps import get_current_user, get_current_user_optional
from app.services.event_service import (
    list_published_events,
    get_event_details,
    add_event_rsvp,
    remove_event_rsvp,
    add_event_interest,
    remove_event_interest,
    create_organizer_event,
    EventNotFoundError,
    EventValidationError
)

from app.services.storage_service import storage_service, ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE, validate_image_bytes

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("/upload-cover")
async def upload_event_cover(
    file: UploadFile = File(...)
):
    """
    Uploads an event cover or organization media image.
    Validates MIME type, file size limit (5MB), and magic bytes.
    Saves image to persistent storage (S3 or persistent volume/disk) and returns URL.
    """
    content = await file.read()
    url = await storage_service.save_image(
        content=content,
        content_type=file.content_type or "",
        folder="covers"
    )
    return {"url": url}


@router.get("", response_model=EventListResponse)
async def discover_events(
    city_id: Optional[str] = Query(None, description="City ID filter, e.g. 'makhachkala'"),
    category_id: Optional[str] = Query(None, description="Category slug/ID filter, e.g. 'concerts'"),
    date_filter: str = Query("all", pattern="^(all|today|tomorrow|weekend)$", description="Date filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db)
):
    """
    Public event discovery feed. Returns published events filtered by city, category, and date.
    Calculates date boundaries according to the selected city's timezone.
    """
    # If city not specified, default to user's saved city if authenticated, or makhachkala
    effective_city = city_id or (current_user.default_city_id if current_user and current_user.default_city_id else "makhachkala")

    events, total = await list_published_events(
        session=session,
        city_id=effective_city,
        category_id=category_id,
        date_filter=date_filter,
        current_user_id=current_user.id if current_user else None,
        limit=limit,
        offset=offset
    )

    return EventListResponse(
        events=events,
        total=total,
        city_id=effective_city,
        category_id=category_id,
        date_filter=date_filter
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db)
):
    """
    Fetches full event details including description, address, and current user RSVP status.
    """
    try:
        user_id = current_user.id if current_user else None
        event = await get_event_details(session, event_id, current_user_id=user_id)
        return event
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{event_id}/rsvp", response_model=RSVPResponse)
async def rsvp_event(
    event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Idempotent RSVP creation: marks user as attending ('Я иду').
    Repeated POST calls safely return existing state without duplicate entries or double-counting.
    """
    try:
        is_attending, count, msg = await add_event_rsvp(session, event_id, user.id)
        return RSVPResponse(
            event_id=event_id,
            is_attending=is_attending,
            attendee_count=count,
            message=msg
        )
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{event_id}/rsvp", response_model=RSVPResponse)
async def cancel_rsvp_event(
    event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Idempotent RSVP cancellation: removes attendance record.
    Repeated DELETE calls are safe and repeatable.
    """
    try:
        is_attending, count, msg = await remove_event_rsvp(session, event_id, user.id)
        return RSVPResponse(
            event_id=event_id,
            is_attending=is_attending,
            attendee_count=count,
            message=msg
        )
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{event_id}/interest", response_model=EventInterestResponse)
async def express_event_interest(
    event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Idempotent interest creation: marks user as interested ('Хочу пойти').
    If user was previously attending ('Я иду'), switches status to interested.
    Repeated POST calls safely return existing state without duplicate entries.
    """
    try:
        is_interested, int_count, is_attending, att_count, msg = await add_event_interest(session, event_id, user.id)
        return EventInterestResponse(
            event_id=event_id,
            is_interested=is_interested,
            interest_count=int_count,
            is_attending=is_attending,
            attendee_count=att_count,
            message=msg
        )
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{event_id}/interest", response_model=EventInterestResponse)
async def remove_event_interest_endpoint(
    event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Idempotent interest cancellation: removes interest record ('Хочу пойти').
    Repeated DELETE calls are safe and repeatable.
    """
    try:
        is_interested, int_count, is_attending, att_count, msg = await remove_event_interest(session, event_id, user.id)
        return EventInterestResponse(
            event_id=event_id,
            is_interested=is_interested,
            interest_count=int_count,
            is_attending=is_attending,
            attendee_count=att_count,
            message=msg
        )
    except EventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Submits a new event by an organizer. Always enters 'pending' state for admin moderation.
    """
    try:
        event = await create_organizer_event(session, payload, organizer_user_id=user.id)
        # Fetch detailed view for response
        return await get_event_details(session, event.id, current_user_id=user.id)
    except HTTPException:
        raise
    except EventValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
