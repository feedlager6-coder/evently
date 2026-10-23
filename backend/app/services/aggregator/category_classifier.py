import re
from typing import Optional, List


# 1. STANDUP / HUMOR KEYWORDS -> 'parties' (never 'theatre')
STANDUP_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'стендап|standup|stand-up|stand\s+up|открытый\s+микрофон|open\s+mic|'
    r'импровизаци[яи]|прожарк[аеи]|юмористическ[а-я]*|квн|комик[а-я]*|'
    r'comedy|шутк[а-я]*|сольник\s+комика'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 2. KIDS / FAMILY KEYWORDS -> 'other' (or 'theatre' if explicitly a fairytale play; never 'concerts')
KIDS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'детск[а-я]*|для\s+детей|детям|утренник[а-я]*|кукольн[а-я]*|сказк[а-я]*|'
    r'мультконцерт[а-я]*|цирк[а-я]*|\bиллюзионист[а-я]*\b|\bфокусник[а-я]*\b|мыльных\s+пузырей|'
    r'три\s+кота|синий\s+трактор|фиксик[а-я]*|барбоскин[а-я]*|детский\s+спектакль|'
    r'свинка\s+пеппа|чебурашк[а-я]*|бременские\s+музыканты'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 3. THEATRE KEYWORDS -> 'theatre'
THEATRE_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'спектакл[а-я]*|спектал[а-я]*|театр[а-я]*|драм[а-я]*|комеди[яи]|трагеди[яи]|'
    r'балет[а-я]*|опер[а-я]*|мюзикл[а-я]*|оперетт[а-я]*|постановк[а-я]*|'
    r'моноспектакл[а-я]*|щелкунчик[а-я]*|лебединое\s+озеро|антреприз[а-я]*|'
    r'пьес[а-я]*|гастроли\s+театра'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 4. SPORTS KEYWORDS -> 'sports'
SPORTS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'матч[а-я]*|турнир[а-я]*|чемпионат[а-я]*|футбол[а-я]*|борьб[а-я]*|'
    r'мма|mma|бокс[а-я]*|единоборств[а-я]*|хоккей[а-я]*|баскетбол[а-я]*|'
    r'кубок[а-я]*|забег[а-я]*|марафон[а-я]*|дзюдо|самбо|волейбол[а-я]*|'
    r'фигурное\s+катание'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 5. EXHIBITIONS / ART -> 'exhibitions'
EXHIBITIONS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'выставк[а-я]*|экспозици[а-я]*|галере[а-я]*|музе[а-я]*|вернисаж[а-я]*|'
    r'планетари[а-я]*|живопис[а-я]*|фотовыставк[а-я]*|арт-пространств[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 6. EDUCATION / LECTURES -> 'education'
EDUCATION_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'лекци[яие]*|мастер-класс[а-я]*|воркшоп[а-я]*|семинар[а-я]*|тренинг[а-я]*|'
    r'митап[а-я]*|курсы|обучени[ея]|вебинар[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 7. BUSINESS -> 'business'
BUSINESS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'бизнес[а-я]*|нетворк[а-я]*|стартап[а-я]*|инвестици[яие]*|'
    r'форум[а-я]*|конференци[яие]*|круглый\s+стол'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 8. CONCERTS / MUSIC -> 'concerts'
CONCERTS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'концерт[а-я]*|симфоническ[а-я]*|оркестр[а-я]*|трибьют[а-я]*|tribute|'
    r'рок(?![а-яё])|рэп|джаз[а-я]*|неоклассик[а-я]*|орган[а-я]*|филармони[яие]*|'
    r'хор(?![а-яё])|ансамбл[ьяе]*|сольник|гитар[а-я]*|вокал[а-я]*|'
    r'музыкальн[а-я]*|live\s+band|песни|cover\s+band|кавер-групп[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# Rubric fallback mapping
RUBRIC_FALLBACK_MAP = {
    "concert": "concerts",
    "concerts": "concerts",
    "music": "concerts",
    "classical_music": "concerts",
    "theatre": "theatre",
    "theater": "theatre",
    "theatre_show": "theatre",
    "ballet": "theatre",
    "musical": "theatre",
    "opera": "theatre",
    "standup": "parties",
    "comedy": "parties",
    "humor": "parties",
    "party": "parties",
    "parties": "parties",
    "club": "parties",
    "show": "parties",
    "sport": "sports",
    "sports": "sports",
    "match": "sports",
    "exhibition": "exhibitions",
    "exhibitions": "exhibitions",
    "museum": "exhibitions",
    "art": "exhibitions",
    "education": "education",
    "lecture": "education",
    "workshop": "education",
    "business": "business",
    "conference": "business",
    "kids": "other",
    "children": "other",
    "circus": "other",
    "other": "other",
}


def classify_event_category(
    title: str = "",
    description: str = "",
    raw_rubric: Optional[str] = None,
    age_restriction: Optional[str] = None,
    venue_name: Optional[str] = None,
) -> str:
    """
    Two-tier robust category classifier.
    Tier 1: Priority keyword analysis on title and description.
    Tier 2: Platform source rubric fallback mapping.
    """
    t_clean = (title or "").strip().lower().replace('ё', 'е')
    d_clean = (description or "")[:500].strip().lower().replace('ё', 'е')
    v_clean = (venue_name or "").strip().lower().replace('ё', 'е')
    combined = f"{t_clean} {d_clean}".strip()

    # --- TIER 1: HIGH PRIORITY KEYWORD RULES ---

    # 1. Standup & Humor: highest priority (NEVER theatre, NEVER concerts)
    if STANDUP_PATTERN.search(t_clean) or STANDUP_PATTERN.search(d_clean):
        return "parties"

    # 2. Sports: very specific keywords
    if SPORTS_PATTERN.search(t_clean) or (SPORTS_PATTERN.search(d_clean) and not THEATRE_PATTERN.search(t_clean)):
        return "sports"

    # 3. Kids / Family:
    # If explicitly a fairy-tale theater play (e.g. "Детский спектакль", "Сказка в театре"), goes to 'theatre'
    # Otherwise (circus, soap bubbles, cartoon concert, puppet show, morning) goes to 'other' (NEVER 'concerts')
    if KIDS_PATTERN.search(t_clean) or (age_restriction in ["0+", "6+"] and KIDS_PATTERN.search(d_clean)):
        if "спектакл" in t_clean or "театр" in t_clean or "балет" in t_clean:
            return "theatre"
        return "other"

    # 4. Education / Lectures / Workshops (takes precedence over exhibition if it's a workshop/masterclass)
    if EDUCATION_PATTERN.search(t_clean):
        return "education"

    # 5. Exhibitions & Art:
    if EXHIBITIONS_PATTERN.search(t_clean):
        return "exhibitions"

    # 6. Business:
    if BUSINESS_PATTERN.search(t_clean):
        return "business"

    # 7. Theatre / Ballet / Opera / Drama:
    if THEATRE_PATTERN.search(t_clean):
        return "theatre"
    if "театр" in v_clean and not CONCERTS_PATTERN.search(t_clean) and not STANDUP_PATTERN.search(t_clean):
        return "theatre"

    # 8. Concerts / Live Music:
    if CONCERTS_PATTERN.search(t_clean):
        return "concerts"

    # Secondary checks in description if title was ambiguous
    if EXHIBITIONS_PATTERN.search(d_clean):
        return "exhibitions"
    if THEATRE_PATTERN.search(d_clean):
        return "theatre"
    if CONCERTS_PATTERN.search(d_clean):
        return "concerts"
    if EDUCATION_PATTERN.search(d_clean):
        return "education"

    # --- TIER 2: SOURCE RUBRIC FALLBACK ---
    if raw_rubric:
        rubric_norm = raw_rubric.lower().strip().replace('/', '').replace('-', '_')
        for key, cat_id in RUBRIC_FALLBACK_MAP.items():
            if key in rubric_norm:
                return cat_id

    return "other"
