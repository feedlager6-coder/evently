from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class TelegramUserPayload(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    language_code: Optional[str] = None


class TelegramInitDataParsed(BaseModel):
    user: TelegramUserPayload
    auth_date: int
    hash: str
    query_id: Optional[str] = None
    chat_type: Optional[str] = None
    chat_instance: Optional[str] = None
    start_param: Optional[str] = None
    raw_data: Dict[str, str] = Field(default_factory=dict)
