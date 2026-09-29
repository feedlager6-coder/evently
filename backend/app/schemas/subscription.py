from datetime import datetime
from typing import List
from pydantic import BaseModel
from app.schemas.organization import OrganizationSummary


class SubscriptionStatusResponse(BaseModel):
    is_subscribed: bool
    followers_count: int
    message: str


class UserSubscriptionItem(BaseModel):
    id: str
    organization: OrganizationSummary
    created_at: datetime
