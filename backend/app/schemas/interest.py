from pydantic import BaseModel


class EventInterestResponse(BaseModel):
    event_id: str
    is_interested: bool
    interest_count: int
    is_attending: bool = False
    attendee_count: int = 0
    message: str
