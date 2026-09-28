from pydantic import BaseModel


class RSVPResponse(BaseModel):
    event_id: str
    is_attending: bool
    attendee_count: int
    message: str
