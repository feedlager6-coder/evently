from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class BroadcastTargetType(str, Enum):
    ORGANIZATION_SUBSCRIBERS = "organization_subscribers"
    EVENT_INTEREST = "event_interest"


class BroadcastType(str, Enum):
    MARKETING = "marketing"
    TRANSACTIONAL = "transactional"


class BroadcastTemplateKey(str, Enum):
    EVENT_ANNOUNCEMENT = "event_announcement"
    EVENT_UPDATE = "event_update"
    CUSTOM_UPDATE = "custom_update"


class BroadcastStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BroadcastPreviewRequest(BaseModel):
    organization_id: str = Field(..., description="Organization ID sending the broadcast")
    target_type: str = Field(
        default=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        description="Target audience type"
    )
    broadcast_type: str = Field(
        default=BroadcastType.MARKETING.value,
        description="Marketing or transactional broadcast"
    )
    template_key: str = Field(
        default=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        description="Message template"
    )
    event_id: Optional[str] = Field(None, description="Event ID (required for event-related templates)")
    custom_text: Optional[str] = Field(None, max_length=500, description="Optional custom message text (max 500 chars)")


class BroadcastPreviewResponse(BaseModel):
    organization_id: str
    organization_name: str
    target_type: str
    broadcast_type: str
    template_key: str
    event_id: Optional[str] = None
    event_title: Optional[str] = None
    total_audience: int = Field(..., description="Total users in this category")
    eligible_recipients: int = Field(..., description="Actual recipient count who will receive message")
    disabled_notifications_count: int = Field(..., description="Users who disabled notifications")
    fatigued_recipients_count: int = Field(..., description="Users excluded due to 24h fatigue rule")
    preview_text: str = Field(..., description="Sanitized Telegram HTML preview text")
    preview_button_text: str = Field(..., description="CTA button text")
    preview_button_url: str = Field(..., description="Deep-link CTA URL")
    cover_image_url: Optional[str] = Field(None, description="Event cover image URL if broadcast includes photo")


class BroadcastCreateRequest(BaseModel):
    organization_id: str = Field(..., description="Organization ID sending the broadcast")
    target_type: str = Field(
        default=BroadcastTargetType.ORGANIZATION_SUBSCRIBERS.value,
        description="Target audience type"
    )
    broadcast_type: str = Field(
        default=BroadcastType.MARKETING.value,
        description="Marketing or transactional broadcast"
    )
    template_key: str = Field(
        default=BroadcastTemplateKey.EVENT_ANNOUNCEMENT.value,
        description="Message template"
    )
    event_id: Optional[str] = Field(None, description="Event ID (required for event-related templates)")
    custom_text: Optional[str] = Field(None, max_length=500, description="Optional custom message text (max 500 chars)")


class BroadcastItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    organization_name: str
    event_id: Optional[str] = None
    event_title: Optional[str] = None
    target_type: str
    broadcast_type: str
    template_key: str
    custom_text: Optional[str] = None
    status: str
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    blocked_count: int
    opened_count: int = 0
    interest_count: int = 0
    rsvp_count: int = 0
    open_rate: float = 0.0
    interest_conversion: float = 0.0
    rsvp_conversion: float = 0.0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BroadcastDetail(BroadcastItem):
    message_text: str
    button_text: str
    button_url: str
    attribution_token: Optional[str] = None

