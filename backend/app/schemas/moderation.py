from typing import Optional
from pydantic import BaseModel, Field


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Optional rejection reason provided by admin")
