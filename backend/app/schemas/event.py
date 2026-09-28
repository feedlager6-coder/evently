from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl, ConfigDict, field_validator


class EventCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Event title")
    description: str = Field(..., min_length=10, max_length=5000, description="Event description")
    cover_image_url: Optional[str] = Field(None, max_length=1024, description="HTTPS image cover URL")
    category_id: str = Field(..., description="ID of the category (e.g. concerts, sports)")
    city_id: str = Field(..., description="ID of the city (e.g. warsaw, makhachkala, moscow)")
    start_at: datetime = Field(..., description="Start timestamp with timezone")
    venue_name: str = Field(..., min_length=2, max_length=255, description="Venue name")
    address: str = Field(..., min_length=2, max_length=255, description="Physical address")
    price_amount: Optional[float] = Field(None, ge=0, description="Admission price (null if free)")
    price_currency: Optional[str] = Field(None, max_length=10, description="Price currency (e.g. PLN, RUB)")

    @field_validator("cover_image_url")
    @classmethod
    def validate_cover_image(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("cover_image_url must start with http:// or https://")
        return v


class EventSummary(BaseModel):
    id: str
    title: str
    cover_image_url: Optional[str] = None
    category_id: str
    category_name: Optional[str] = None
    city_id: str
    city_name: Optional[str] = None
    start_at: datetime
    venue_name: str
    price_amount: Optional[float] = None
    price_currency: Optional[str] = None
    is_free: bool = True
    attendee_count: int = 0
    status: str
    is_attending: bool = False

    model_config = ConfigDict(from_attributes=True)


class EventResponse(EventSummary):
    description: str
    address: str
    organizer_user_id: int
    organizer_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    events: List[EventSummary]
    total: int
    city_id: Optional[str] = None
    category_id: Optional[str] = None
    date_filter: Optional[str] = "all"
