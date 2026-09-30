from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyStatusResponse(BaseModel):
    event_id: str
    is_opted_in: bool = False
    is_active: bool = False
    note: Optional[str] = None
    active_members_count: int = 0
    pending_incoming_count: int = 0
    matches_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CompanyProfilePayload(BaseModel):
    is_active: bool = True
    note: Optional[str] = None

    @field_validator("note")
    @classmethod
    def validate_note_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 140:
                raise ValueError("Длина заметки не может превышать 140 символов")
            return v if v else None
        return None


class CompanyMemberItem(BaseModel):
    """
    Public company seeker item.
    Strict privacy: zero telegram_id, zero username, zero joined_at.
    """
    user_id: int
    first_name: str
    avatar_url: Optional[str] = None
    attendance_status: str = "interested"  # "attending" | "interested"
    note: Optional[str] = None
    relationship_status: str = "none"  # "none" | "sent_pending" | "received_pending" | "matched"

    model_config = ConfigDict(from_attributes=True)


class CompanyRequestCreate(BaseModel):
    target_user_id: int


class CompanyRequestItem(BaseModel):
    request_id: str
    event_id: str
    other_user_id: int
    other_first_name: str
    other_avatar_url: Optional[str] = None
    other_attendance_status: str = "interested"
    note: Optional[str] = None
    direction: str  # "incoming" | "outgoing"
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyRequestsResponse(BaseModel):
    incoming: List[CompanyRequestItem] = []
    outgoing: List[CompanyRequestItem] = []


class CompanyMatchItem(BaseModel):
    match_id: str
    event_id: str
    partner_id: int
    partner_first_name: str
    partner_avatar_url: Optional[str] = None
    partner_attendance_status: str = "interested"
    partner_telegram_username: Optional[str] = None
    partner_telegram_url: Optional[str] = None
    has_telegram_username: bool = False
    matched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyActionResponse(BaseModel):
    ok: bool = True
    message: str
    match_created: bool = False
    match: Optional[CompanyMatchItem] = None
