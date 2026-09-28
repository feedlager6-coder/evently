import re
from typing import Optional, NamedTuple


class ParsedQuery(NamedTuple):
    city_id: Optional[str]
    category_id: Optional[str]
    date_filter: str  # "all", "today", "tomorrow", "weekend"
    is_ambiguous: bool
    raw_query: str


CITY_PATTERNS = {
    "warsaw": [r"\bваршав[аеуыо]?\b", r"\bwarsaw\b"],
    "makhachkala": [r"\bмахачкал[аеуыо]?\b", r"\bmakhachkala\b"],
    "moscow": [r"\bмоскв[аеуыо]?\b", r"\bmoscow\b"],
}

CATEGORY_PATTERNS = {
    "concerts": [r"\bконцерт[а-я]*\b", r"\bмузык[а-я]*\b", r"\bживой звук\b", r"\blive\b", r"\bрок\b", r"\bджаз\b"],
    "parties": [r"\bвечеринк[а-я]*\b", r"\bтусовк[а-я]*\b", r"\bклуб[а-я]*\b", r"\bдискотек[а-я]*\b", r"\bрейв\b", r"\bparty\b"],
    "sports": [r"\bспорт[а-я]*\b", r"\bматч[а-я]*\b", r"\bфутбол[а-я]*\b", r"\bмарафон[а-я]*\b", r"\bфитнес[а-я]*\b", r"\bтурнир[а-я]*\b"],
    "education": [r"\bобразовани[а-я]*\b", r"\bлекци[а-я]*\b", r"\bмитап[а-я]*\b", r"\bворкшоп[а-я]*\b", r"\bсеминар[а-я]*\b", r"\bмастер-класс[а-я]*\b", r"\bmeetup\b"],
    "business": [r"\bбизнес[а-я]*\b", r"\bнетворк[а-я]*\b", r"\bстартап[а-я]*\b", r"\bконференци[а-я]*\b", r"\bинвестиц[а-я]*\b"],
    "exhibitions": [r"\bвыставк[а-я]*\b", r"\bгалере[а-я]*\b", r"\bмузе[а-я]*\b", r"\bарт\b", r"\bэкспозици[а-я]*\b"],
    "other": [r"\bдруг[а-я]+\b", r"\bпроче[ее]\b"],
}

DATE_PATTERNS = {
    "today": [r"\bсегодня\b", r"\btoday\b", r"\bсейчас\b"],
    "tomorrow": [r"\bзавтра\b", r"\btomorrow\b"],
    "weekend": [r"\bвыходн[а-я]*\b", r"\bсуббот[а-я]*\b", r"\bвоскресень[а-я]*\b", r"\bweekend\b"],
}


def parse_query(raw_query: str, default_city_id: Optional[str] = None) -> ParsedQuery:
    """
    Deterministic rule-based query parser (zero LLM dependency).
    Extracts city, category, and date filter from user inputs such as:
    - 'мероприятия в Варшаве'
    - 'концерты в Москве'
    - 'события сегодня'
    - 'спорт в Махачкале на выходных'
    """
    text = (raw_query or "").strip().lower()

    city_id: Optional[str] = None
    category_id: Optional[str] = None
    date_filter = "all"

    # Match city
    for cid, patterns in CITY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                city_id = cid
                break
        if city_id:
            break

    # Match category
    for cat_id, patterns in CATEGORY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                category_id = cat_id
                break
        if category_id:
            break

    # Match date
    for d_filter, patterns in DATE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                date_filter = d_filter
                break
        if date_filter != "all":
            break

    # Fallback to default city if not explicitly specified
    if not city_id and default_city_id:
        city_id = default_city_id

    # An empty or completely unrecognized query without any city is ambiguous
    is_ambiguous = (city_id is None)

    return ParsedQuery(
        city_id=city_id,
        category_id=category_id,
        date_filter=date_filter,
        is_ambiguous=is_ambiguous,
        raw_query=raw_query
    )
