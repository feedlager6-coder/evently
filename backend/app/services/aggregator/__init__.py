from app.services.aggregator.models import AggregatedEvent
from app.services.aggregator.category_classifier import classify_event_category
from app.services.aggregator.deduplication import (
    normalize_event_title,
    normalize_venue,
    calculate_title_similarity,
    is_cross_platform_duplicate,
)
from app.services.aggregator.kassir_parser import KassirParser
from app.services.aggregator.mts_live_parser import MtsLiveParser
from app.services.aggregator.yandex_afisha_parser import YandexAfishaParser
from app.services.aggregator.aggregator_service import AggregatorMasterService

__all__ = [
    "AggregatedEvent",
    "classify_event_category",
    "normalize_event_title",
    "normalize_venue",
    "calculate_title_similarity",
    "is_cross_platform_duplicate",
    "KassirParser",
    "MtsLiveParser",
    "YandexAfishaParser",
    "AggregatorMasterService",
]
