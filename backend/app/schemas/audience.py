from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class OrganizationAudienceItem(BaseModel):
    id: str
    name: str
    slug: str
    avatar_url: Optional[str] = None
    category: str
    city_name: Optional[str] = None
    subscribers_count: int = 0
    new_subscribers_7d: int = 0
    new_subscribers_30d: int = 0
    events_count: int = 0
    total_views: int = 0
    total_interest: int = 0
    total_attendees: int = 0

    model_config = ConfigDict(from_attributes=True)


class EventAudienceItem(BaseModel):
    id: str
    title: str
    start_at: datetime
    venue_name: str
    status: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    views_count: int = 0
    interest_count: int = 0
    attendee_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class OrganizerAudienceResponse(BaseModel):
    total_subscribers: int = 0
    new_subscribers_7d: int = 0
    new_subscribers_30d: int = 0
    total_views: int = 0
    total_interest: int = 0
    total_attendees: int = 0
    total_unique_engaged: int = 0
    organizations: List[OrganizationAudienceItem] = []
    recent_events: List[EventAudienceItem] = []

    model_config = ConfigDict(from_attributes=True)
