from typing import Optional
from pydantic import BaseModel, ConfigDict


class CityResponse(BaseModel):
    id: str
    name: str
    country: str
    timezone: str
    currency: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

