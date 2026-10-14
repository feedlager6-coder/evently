from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Organization name")
    category: str = Field(..., min_length=2, max_length=50, description="Organization category")
    description: Optional[str] = Field(None, max_length=5000, description="Organization description")
    city_id: Optional[str] = Field(None, max_length=50, description="City ID, e.g. 'makhachkala'")
    address: Optional[str] = Field(None, max_length=255, description="Physical address")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    avatar_url: Optional[str] = Field(None, max_length=1024, description="Avatar image URL")
    website: Optional[str] = Field(None, max_length=1024, description="Website URL")
    social_link: Optional[str] = Field(None, max_length=1024, description="Social media link or Telegram channel")
    features: Optional[List[str]] = Field(None, description="Venue rules and features tags")

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip()
        if not val:
            return None
        low = val.lower()
        for bad in ("javascript:", "data:", "vbscript:", "file:"):
            if low.startswith(bad):
                raise ValueError(f"Недопустимая схема URL: {bad}")
        if val.startswith("//"):
            raise ValueError("avatar_url не может быть protocol-relative (начинаться с //)")
        if not (val.startswith("http://") or val.startswith("https://") or val.startswith("/uploads/")):
            raise ValueError("avatar_url должен начинаться с http://, https:// или /uploads/")
        return val

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip()
        if not val:
            return None
        low = val.lower()
        for bad in ("javascript:", "data:", "vbscript:", "file:"):
            if low.startswith(bad):
                raise ValueError(f"Недопустимая схема URL: {bad}")
        if not (val.startswith("http://") or val.startswith("https://")):
            return f"https://{val}"
        return val

    @field_validator("social_link")
    @classmethod
    def validate_social_link(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip()
        if not val:
            return None
        low = val.lower()
        for bad in ("javascript:", "data:", "vbscript:", "file:"):
            if low.startswith(bad):
                raise ValueError(f"Недопустимая схема URL: {bad}")
        if val.startswith("@"):
            return f"https://t.me/{val[1:]}"
        if val.startswith("t.me/"):
            return f"https://{val}"
        if val.startswith("vk.com/"):
            return f"https://{val}"
        if not (val.startswith("http://") or val.startswith("https://")):
            return f"https://{val}"
        return val


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    category: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=5000)
    city_id: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = Field(None)
    longitude: Optional[float] = Field(None)
    avatar_url: Optional[str] = Field(None, max_length=1024)
    website: Optional[str] = Field(None, max_length=1024)
    social_link: Optional[str] = Field(None, max_length=1024)
    features: Optional[List[str]] = Field(None)
    status: Optional[str] = Field(None, pattern="^(active|disabled)$")

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip()
        if not val:
            return None
        low = val.lower()
        for bad in ("javascript:", "data:", "vbscript:", "file:"):
            if low.startswith(bad):
                raise ValueError(f"Недопустимая схема URL: {bad}")
        if val.startswith("//"):
            raise ValueError("avatar_url не может быть protocol-relative (начинаться с //)")
        if not (val.startswith("http://") or val.startswith("https://") or val.startswith("/uploads/")):
            raise ValueError("avatar_url должен начинаться с http://, https:// или /uploads/")
        return val

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip()
        if not val:
            return None
        low = val.lower()
        for bad in ("javascript:", "data:", "vbscript:", "file:"):
            if low.startswith(bad):
                raise ValueError(f"Недопустимая схема URL: {bad}")
        if not (val.startswith("http://") or val.startswith("https://")):
            return f"https://{val}"
        return val

    @field_validator("social_link")
    @classmethod
    def validate_social_link(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        val = v.strip()
        if not val:
            return None
        low = val.lower()
        for bad in ("javascript:", "data:", "vbscript:", "file:"):
            if low.startswith(bad):
                raise ValueError(f"Недопустимая схема URL: {bad}")
        if val.startswith("@"):
            return f"https://t.me/{val[1:]}"
        if val.startswith("t.me/"):
            return f"https://{val}"
        if val.startswith("vk.com/"):
            return f"https://{val}"
        if not (val.startswith("http://") or val.startswith("https://")):
            return f"https://{val}"
        return val


class OrganizationSummary(BaseModel):
    id: str
    name: str
    slug: str
    category: str
    city_id: Optional[str] = None
    city_name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    avatar_url: Optional[str] = None
    features: Optional[List[str]] = None
    status: str = "active"
    is_verified: bool = False
    followers_count: int = 0
    events_count: int = 0
    is_subscribed: bool = False
    is_owner: bool = False
    plan: Optional[str] = "free"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationResponse(OrganizationSummary):
    description: Optional[str] = None
    website: Optional[str] = None
    social_link: Optional[str] = None
    owner_user_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationListResponse(BaseModel):
    organizations: List[OrganizationSummary]
    total: int
