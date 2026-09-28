from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
