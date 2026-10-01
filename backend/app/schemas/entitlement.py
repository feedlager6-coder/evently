from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    LOCKED = "locked"
    COMING_SOON = "coming_soon"


class CapabilityInfo(BaseModel):
    key: str
    title: str
    description: str
    status: CapabilityStatus
    is_pro_feature: bool
    limit: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class EntitlementLimits(BaseModel):
    broadcasts_per_month: int
    broadcasts_used_this_month: int
    broadcasts_remaining: int

    model_config = ConfigDict(from_attributes=True)


class OrganizerEntitlementsResponse(BaseModel):
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    plan: str  # "free" | "pro"
    status: str  # "active" | "expired" | "cancelled"
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    capabilities: Dict[str, CapabilityInfo]
    limits: EntitlementLimits

    model_config = ConfigDict(from_attributes=True)


class SetPlanRequest(BaseModel):
    plan: str
    status: Optional[str] = "active"
    expires_in_days: Optional[int] = None


class AdminOrganizationSummary(BaseModel):
    id: str
    name: str
    slug: str
    category: str
    city_id: str
    owner_user_id: int
    status: str
    plan: str = "free"
    plan_status: str = "active"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

