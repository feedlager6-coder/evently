from pydantic import BaseModel


class RSVPResponse(BaseModel):
    event_id: str
    is_attending: bool
    attendee_count: int
    is_interested: bool = False
    interest_count: int = 0
    message: str
