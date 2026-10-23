import re
import difflib
from datetime import datetime, timezone
from typing import Optional, Set, Tuple


NOISE_WORDS: Set[str] = {
    'концерт', 'концерты', 'концерта', 'концерте',
    'большой', 'большая', 'большое', 'большие',
    'сольный', 'сольная', 'сольное', 'сольные', 'сольник',
    'спектакль', 'спектакли', 'спектакля',
    'шоу', 'вечер', 'стендап', 'standup', 'stand-up', 'stand up',
    'премьера', 'гастроли', 'тур', 'турне', 'юбилейный', 'юбилей',
    'лучшее', 'новое', 'презентация', 'альбома', 'акустика', 'live',
    'программа', 'фестиваль', 'праздник', 'мероприятие',
    'в', 'во', 'на', 'и', 'с', 'со', 'по', 'для', 'от', 'до', 'к', 'ко',
}

CITY_NAMES_NOISE: Set[str] = {
    'москва', 'москве', 'москву', 'москвой', 'мск',
    'санкт-петербург', 'петербург', 'петербурге', 'питер', 'питере', 'спб',
    'махачкала', 'махачкале', 'махачкалу', 'махачкалы',
    'дербент', 'дербенте', 'каспийск', 'каспийске', 'хасавюрт', 'хасавюрте', 'избербаш',
    'казань', 'казани', 'казанью',
    'краснодар', 'краснодаре', 'сочи',
    'ростов-на-дону', 'ростове', 'ростов',
    'екатеринбург', 'екатеринбурге', 'екб',
    'новосибирск', 'новосибирске',
    'нижний новгород', 'нижнем новгороде',
    'самара', 'самаре', 'уфа', 'уфе',
    'красноярск', 'красноярске', 'воронеж', 'воронеже',
    'волгоград', 'волгограде', 'грозный', 'грозном',
    'владикавказ', 'владикавказе', 'нальчик', 'нальчике',
    'пятигорск', 'пятигорске', 'ставрополь', 'ставрополе',
    'челябинск', 'челябинске', 'тюмень', 'тюмени', 'омск', 'омске',
    'пермь', 'перми', 'саратов', 'саратове', 'ярославль', 'ярославле',
    'калининград', 'калининграде', 'владивосток', 'владивостоке',
    'хабаровск', 'хабаровске', 'иркутск', 'иркутске', 'барнаул', 'барнауле',
    'томск', 'томске', 'кемерово', 'кемерове', 'новокузнецк', 'новокузнецке',
}

VENUE_PREFIXES = [
    r'\bдворец\s+спорта\b', r'\bдс\b',
    r'\bдом\s+культуры\b', r'\bдк\b',
    r'\bконцертный\s+зал\b', r'\bкз\b',
    r'\bгосударственный\b', r'\bакадемический\b',
    r'\bтеатр\b', r'\bклуб\b', r'\bарена\b', r'\bстадион\b',
    r'\bим\.\b', r'\bим\b', r'\bимени\b',
    r'\bзал\b', r'\bхолл\b', r'\bлофт\b', r'\bбар\b', r'\bресторан\b',
]


def stem_russian_noun(word: str) -> str:
    """
    Strips common genitive / inflectional endings from Russian artist names
    (e.g., 'Басты' -> 'баста', 'Мота' -> 'мот', 'Елки' -> 'елка', 'Кузьмина' -> 'кузьмин').
    """
    w = word.lower().replace('ё', 'е')
    if len(w) <= 3:
        return w
    # Common genitive/accusative patronymics and surnames
    for suf in ['ова', 'ева', 'ина', 'ына', 'ого', 'его']:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[:-1]  # 'газманова' -> 'газманов'
    # Simple -ы / -и / -а / -я endings for names like 'басты' -> 'баста'
    if w.endswith('ы') or w.endswith('и'):
        return w[:-1] + 'а'
    return w


def normalize_event_title(title: str) -> str:
    """
    Normalizes event title for high-precision cross-platform fuzzy matching:
    1. Lowercase, 'ё' -> 'е'.
    2. Strips age ratings ('0+', '12+', '18+', etc.).
    3. Strips quotes, brackets, and punctuation.
    4. Removes common filler/noise words and city mentions.
    5. Normalizes Russian inflections for artist names.
    """
    if not title:
        return ""
    text = title.lower().replace('ё', 'е')
    # Remove age ratings: 0+, 6+, 12+, 16+, 18+
    text = re.sub(r'\b\d{1,2}\+', ' ', text)
    # Remove quotes, punctuation, symbols
    text = re.sub(r'[«»""\'`’–—\-_:;,\.!?\(\)\[\]/\\\|\*&#@]', ' ', text)
    tokens = text.split()

    clean_tokens = []
    for t in tokens:
        if t in NOISE_WORDS or t in CITY_NAMES_NOISE:
            continue
        clean_tokens.append(stem_russian_noun(t))

    if not clean_tokens:
        clean_tokens = [stem_russian_noun(t) for t in tokens if not re.match(r'^\d+$', t)]

    return " ".join(clean_tokens).strip()


def normalize_venue(venue: str) -> str:
    """
    Normalizes venue name by stripping organizational prefixes, 'им.', quotes, and punctuation.
    """
    if not venue:
        return ""
    text = venue.lower().replace('ё', 'е')
    # Remove quotes, punctuation
    text = re.sub(r'[«»""\'`’–—\-_:;,\.!?\(\)\[\]/\\\|\*&#@]', ' ', text)
    # Remove prefixes
    for prefix_pat in VENUE_PREFIXES:
        text = re.sub(prefix_pat, ' ', text, flags=re.IGNORECASE)
    return " ".join(text.split()).strip()


def calculate_title_similarity(t1: str, t2: str) -> float:
    """
    Calculates title similarity score in range [0.0, 1.0] using hybrid
    token Jaccard, SequenceMatcher, and substring core heuristics.
    """
    if not t1 or not t2:
        return 0.0
    if t1 == t2:
        return 1.0

    # Substring core match (>= 4 characters)
    if (len(t1) >= 4 and t1 in t2) or (len(t2) >= 4 and t2 in t1):
        return 0.95

    tokens1 = set(t1.split())
    tokens2 = set(t2.split())
    if tokens1 and tokens2:
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        jaccard = len(intersection) / len(union)
        if jaccard >= 0.5:
            return max(jaccard, 0.75)

    seq_ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
    return seq_ratio


def is_cross_platform_duplicate(
    title_a: str,
    venue_a: str,
    time_a: datetime,
    city_a: str,
    title_b: str,
    venue_b: str,
    time_b: datetime,
    city_b: str,
    max_time_diff_hours: float = 24.0,
    similarity_threshold: float = 0.68,
) -> Tuple[bool, float, str]:
    """
    Evaluates whether two events refer to the exact same event or multiple sessions
    of the same show/tour/excursion on the same calendar day in the same city.
    Returns: (is_duplicate: bool, score: float, reason: str)
    """
    # 1. City must match
    if city_a != city_b:
        return False, 0.0, "Different cities"

    # 2. Date matching (same calendar date in UTC)
    if time_a.tzinfo is None:
        time_a = time_a.replace(tzinfo=timezone.utc)
    if time_b.tzinfo is None:
        time_b = time_b.replace(tzinfo=timezone.utc)

    date_a = time_a.date()
    date_b = time_b.date()
    time_diff_sec = abs((time_a - time_b).total_seconds())

    # If dates are completely different days (and time difference > 4 hours crossing midnight), not duplicate
    if date_a != date_b and time_diff_sec > 4 * 3600:
        return False, 0.0, f"Time difference {time_diff_sec/3600:.1f}h (Different calendar dates {date_a} vs {date_b})"

    # 3. Normalize titles and venues
    norm_t_a = normalize_event_title(title_a)
    norm_t_b = normalize_event_title(title_b)
    norm_v_a = normalize_venue(venue_a)
    norm_v_b = normalize_venue(venue_b)

    score = calculate_title_similarity(norm_t_a, norm_t_b)
    venue_match = bool(norm_v_a and norm_v_b and (norm_v_a == norm_v_b or norm_v_a in norm_v_b or norm_v_b in norm_v_a))

    # Condition A: Same calendar day and normalized title match >= 0.75
    # (Collapses multiple sessions of same excursion/show/performance on the same day)
    if score >= 0.75:
        return True, score, f"Same day multi-session or title match ({score:.2f})"

    # Condition B: High title similarity >= 0.90
    if score >= 0.90:
        return True, score, f"High title similarity ({score:.2f})"

    # Condition C: Similarity >= threshold (0.65) AND (venue match OR close start time within 2 hours)
    if score >= similarity_threshold and (venue_match or time_diff_sec <= 2 * 3600):
        reason = f"Title similarity {score:.2f} + {'venue match' if venue_match else 'time match'}"
        return True, score, reason

    return False, score, f"Similarity {score:.2f} below threshold or venue mismatch"
