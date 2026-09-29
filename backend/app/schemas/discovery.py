from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.schemas.event import EventSummary
from app.schemas.organization import OrganizationSummary


class VenueSummary(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city_id: Optional[str] = None
    city_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    organization_avatar_url: Optional[str] = None
    upcoming_events_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DiscoveryOrganizationSummary(OrganizationSummary):
    events_count: int = 0


class UnifiedDiscoveryResponse(BaseModel):
    query: str
    city_id: Optional[str] = None
    events: List[EventSummary] = []
    organizations: List[OrganizationSummary] = []
    venues: List[VenueSummary] = []
    total_events: int = 0
    total_organizations: int = 0
    total_venues: int = 0

    model_config = ConfigDict(from_attributes=True)
