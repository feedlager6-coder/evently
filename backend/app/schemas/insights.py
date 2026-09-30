from typing import List
from pydantic import BaseModel, ConfigDict


class AudienceGrowthMetrics(BaseModel):
    total_subscribers: int = 0
    new_subscribers_7d: int = 0
    new_subscribers_30d: int = 0
    total_unique_engaged: int = 0

    model_config = ConfigDict(from_attributes=True)


class EventPerformanceTotals(BaseModel):
    total_events: int = 0
    upcoming_events_count: int = 0
    past_events_count: int = 0
    total_views: int = 0
    total_interest: int = 0
    total_rsvps: int = 0

    model_config = ConfigDict(from_attributes=True)


class BroadcastPerformanceTotals(BaseModel):
    total_broadcasts: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_attributed_interest: int = 0
    total_attributed_rsvp: int = 0
    overall_open_rate: float = 0.0
    overall_interest_conversion: float = 0.0
    overall_rsvp_conversion: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ViewSourceMetric(BaseModel):
    source: str
    label: str
    views_count: int = 0
    percentage: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class OrganizerInsightsResponse(BaseModel):
    audience: AudienceGrowthMetrics
    events: EventPerformanceTotals
    broadcasts: BroadcastPerformanceTotals
    sources: List[ViewSourceMetric]
    fact_sentence: str
    has_data: bool = False

    model_config = ConfigDict(from_attributes=True)
