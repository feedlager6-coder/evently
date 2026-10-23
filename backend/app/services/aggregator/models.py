from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AggregatedEvent:
    """
    Standardized event schema extracted from external ticketing platforms
    (Kassir.ru, MTS Live, Yandex.Afisha).
    """
    source_name: str  # 'kassir', 'mts_live', 'yandex_afisha'
    external_id: str
    source_url: str  # Direct purchase / event page URL
    title: str
    description: str
    start_at: datetime  # UTC datetime
    city_id: str
    venue_name: str
    address: str
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_currency: str = "RUB"
    cover_image_url: Optional[str] = None
    age_restriction: Optional[str] = None  # e.g. "0+", "6+", "12+", "16+", "18+"
    category_id: str = "other"
    raw_category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
