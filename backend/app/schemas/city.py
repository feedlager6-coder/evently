from pydantic import BaseModel, ConfigDict


class CityResponse(BaseModel):
    id: str
    name: str
    country: str
    timezone: str
    currency: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
