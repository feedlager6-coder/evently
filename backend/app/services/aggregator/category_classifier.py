import re
from typing import Optional, List


# 1. STANDUP / HUMOR KEYWORDS -> 'parties' (never 'theatre')
STANDUP_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'стендап|standup|stand-up|stand\s+up|открытый\s+микрофон|open\s+mic|'
    r'импровизаци[яие]*|прожарк[аеи]*|юмористическ[а-я]*|квн|комик[а-я]*|'
    r'comedy|шутк[а-я]*|сольник\s+комика|вечер\s+комедии|барная\s+викторина|'
    r'шоу\s+историй|смешной\s+вечер'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 2. EXHIBITIONS / ART / MUSEUMS -> 'exhibitions'
EXHIBITIONS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'выставк[а-я]*|экспозици[а-я]*|галере[а-я]*|музе[а-я]*|вернисаж[а-я]*|'
    r'планетари[а-я]*|живопис[а-я]*|фотовыставк[а-я]*|арт-пространств[а-я]*|'
    r'картин[а-я]*|скульптур[а-я]*|мультимедийн[а-я]*\s+выставк[а-я]*|'
    r'иммерсивн[а-я]*\s+выставк[а-я]*|музейн[а-я]*|коллекци[а-я]*|зал\s+славы|'
    r'инсталляци[а-я]*|шедевр[а-я]*|диорам[а-я]*|особняк[а-я]*|усадьб[а-я]*|'
    r'панорам[а-я]*|историческ[а-я]*\s+экспонат[а-я]*|архитектур[а-я]*\s+выставк[а-я]*|'
    r'биеннале|арт-проект[а-я]*|график[аеи]\s+художник[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 3. EDUCATION / WORKSHOPS / LECTURES / TOURS -> 'education'
EDUCATION_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'лекци[яие]*|мастер-класс[а-я]*|воркшоп[а-я]*|семинар[а-я]*|тренинг[а-я]*|'
    r'митап[а-я]*|курсы|обучени[ея]*|вебинар[а-я]*|квиз[а-я]*|quiz|'
    r'интеллектуальн[а-я]*|экскурси[яие]*|пешеходн[а-я]*|квест[а-я]*|хакатон[а-я]*|'
    r'урок[а-я]*|бесед[а-я]*|чтени[а-я]*|литературн[а-я]*|познавательн[а-я]*|'
    r'заняти[а-я]*|мастерская|лаборатори[яие]*|встреча-знакомств[а-я]*|'
    r'библиотек[а-я]*|настольн[а-я]*\s+игр[а-я]*|киноугадайк[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 4. SPORTS KEYWORDS -> 'sports'
SPORTS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'матч[а-я]*|турнир[а-я]*|чемпионат[а-я]*|футбол[а-я]*|борьб[а-я]*|'
    r'мма|mma|бокс[а-я]*|единоборств[а-я]*|хоккей[а-я]*|баскетбол[а-я]*|'
    r'кубок[а-я]*|забег[а-я]*|марафон[а-я]*|дзюдо|самбо|волейбол[а-я]*|'
    r'фигурное\s+катание|арена\s+битва|бои\s+без\s+правил'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 5. THEATRE / DRAMA / BALLET / OPERA / PUPPETS -> 'theatre'
THEATRE_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'спектакл[а-я]*|спектал[а-я]*|театр[а-я]*|драм[а-я]*|трагеди[яи]|комеди[яие]*|'
    r'балет[а-я]*|опер[а-я]*|мюзикл[а-я]*|оперетт[а-я]*|постановк[а-я]*|'
    r'моноспектакл[а-я]*|щелкунчик[а-я]*|лебединое\s+озеро|антреприз[а-я]*|'
    r'пьес[а-я]*|гастроли\s+театра|кукольн[а-я]*\s+театр[а-я]*|театральн[а-я]*|'
    r'сказк[а-я]*|панк-сказка|сказка\s+о|спектакль-сказка|алиса\s+в\s+стране|'
    r'белоснежк[а-я]*|чудо-юдо'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 6. BUSINESS / CONFERENCES -> 'business'
BUSINESS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'бизнес[а-я]*|нетворк[а-я]*|стартап[а-я]*|инвестици[яие]*|'
    r'форум[а-я]*|конференци[яие]*|круглый\s+стол|питчинг|предпринимател[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 7. CONCERTS / MUSIC / TOURS / ARTISTS -> 'concerts'
CONCERTS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'концерт[а-я]*|симфоническ[а-я]*|оркестр[а-я]*|трибьют[а-я]*|tribute|'
    r'рок(?![а-яё])|рэп|джаз[а-я]*|неоклассик[а-я]*|орган[а-я]*|филармони[яие]*|'
    r'хор(?![а-яё])|ансамбл[ьяе]*|сольник|гитар[а-я]*|вокал[а-я]*|'
    r'музыкальн[а-я]*|live\s+band|песни|cover\s+band|кавер-групп[а-я]*|'
    r'хиты|лучшие\s+хиты|все\s+хиты|стадионный\s+тур|мировой\s+тур|\bтур\b|'
    r'дискотек[а-я]*|супердискотек[а-я]*|звук[а-я]*|энергия\s+звука|'
    r'группа|группировка|\bвиа\b|певица|певец|рок-группа|саундтрек[а-я]*|'
    r'киномузык[а-я]*|акустическ[а-я]*|альбом[а-я]*|презентация\s+альбома|'
    r'рэп-исполнител[а-я]*|эстрадн[а-я]*|симфони[яи]*|виолончел[а-я]*|скрипк[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 8. PARTIES / NIGHTLIFE -> 'parties'
PARTIES_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'вечеринк[а-я]*|party|тусовк[а-я]*|рейв|диджей|dj\s+|dj-|club\s+show|'
    r'клубная\s+вечеринка|afterparty|ночь\s+музыки'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# 9. KIDS / FAMILY (for non-theatrical family events)
KIDS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'детск[а-я]*|для\s+детей|детям|утренник[а-я]*|кукольн[а-я]*|'
    r'мультконцерт[а-я]*|цирк[а-я]*|\bиллюзионист[а-я]*\b|\bфокусник[а-я]*\b|мыльных\s+пузырей|'
    r'три\s+кота|синий\s+трактор|фиксик[а-я]*|барбоскин[а-я]*|'
    r'свинка\s+пеппа|чебурашк[а-я]*|бременские\s+музыканты|купи\s+песика|'
    r'детский\s+праздник'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

# Rubric fallback mapping
RUBRIC_FALLBACK_MAP = {
    # Concerts
    "concert": "concerts",
    "concerts": "concerts",
    "koncert": "concerts",
    "bilety_na_koncert": "concerts",
    "music": "concerts",
    "classical_music": "concerts",
    "klassika": "concerts",
    "rock": "concerts",
    "pop": "concerts",
    "rap": "concerts",
    "jazz": "concerts",
    "vocal": "concerts",

    # Theatre
    "theatre": "theatre",
    "theater": "theatre",
    "theatre_show": "theatre",
    "bilety_v_teatr": "theatre",
    "ballet": "theatre",
    "musical": "theatre",
    "opera": "theatre",
    "drama": "theatre",
    "play": "theatre",

    # Standup & Parties
    "standup": "parties",
    "comedy": "parties",
    "humor": "parties",
    "party": "parties",
    "parties": "parties",
    "club": "parties",
    "show": "parties",
    "shou": "parties",
    "nightlife": "parties",

    # Sports
    "sport": "sports",
    "sports": "sports",
    "bilety_na_sportivnye_meropriyatiya": "sports",
    "match": "sports",

    # Exhibitions & Art & Museums
    "exhibition": "exhibitions",
    "exhibitions": "exhibitions",
    "museum": "exhibitions",
    "muzej": "exhibitions",
    "muzei": "exhibitions",
    "bilety_v_muzej": "exhibitions",
    "bilety_v_muzei": "exhibitions",
    "bilety_v_muzei_i_galerei": "exhibitions",
    "art": "exhibitions",
    "gallery": "exhibitions",
    "exposition": "exhibitions",

    # Education & Workshops & Tours
    "education": "education",
    "lecture": "education",
    "workshop": "education",
    "master_klass": "education",
    "seminar": "education",
    "seminary_i_treningi": "education",
    "ekskursii": "education",
    "ekskursiya": "education",
    "tour": "education",
    "quiz": "education",

    # Business
    "business": "business",
    "conference": "business",
    "forum": "business",

    # Kids
    "kids": "other",
    "children": "other",
    "detyam": "other",
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
    Two-tier robust category classifier with enhanced domain coverage.
    Tier 1: Priority keyword analysis on title, venue, and description.
    Tier 2: Platform source rubric mapping.
    """
    t_clean = (title or "").strip().lower().replace('ё', 'е')
    d_clean = (description or "")[:600].strip().lower().replace('ё', 'е')
    v_clean = (venue_name or "").strip().lower().replace('ё', 'е')

    # --- TIER 1: HIGH PRIORITY KEYWORD RULES ---

    # 1. Standup & Humor: highest priority (NEVER theatre, NEVER concerts)
    if STANDUP_PATTERN.search(t_clean) or STANDUP_PATTERN.search(d_clean):
        return "parties"

    # 2. Sports: very specific keywords
    if SPORTS_PATTERN.search(t_clean) or (SPORTS_PATTERN.search(d_clean) and not THEATRE_PATTERN.search(t_clean) and not CONCERTS_PATTERN.search(t_clean)):
        return "sports"

    # 3. Education / Lectures / Workshops / Tours / Quizzes:
    if EDUCATION_PATTERN.search(t_clean):
        return "education"

    # 4. Exhibitions & Art & Museums:
    if EXHIBITIONS_PATTERN.search(t_clean):
        return "exhibitions"
    if any(m in v_clean for m in ["музей", "галерея", "эрмитаж", "третьяков", "манеж", "планетарий", "выставочный центр", "выставочный зал", "арт-пространство"]):
        if not CONCERTS_PATTERN.search(t_clean) and not THEATRE_PATTERN.search(t_clean) and not STANDUP_PATTERN.search(t_clean):
            return "exhibitions"

    # 5. Theatre / Ballet / Opera / Drama / Stage Fairy Tales:
    if THEATRE_PATTERN.search(t_clean):
        return "theatre"
    if any(th in v_clean for th in ["театр", "тюз", "мхат", "бдт", "мариинский", "малый театр", "кукольный театр", "драмтеатр"]):
        if not CONCERTS_PATTERN.search(t_clean) and not STANDUP_PATTERN.search(t_clean) and not SPORTS_PATTERN.search(t_clean):
            return "theatre"

    # 6. Parties / Nightlife:
    if PARTIES_PATTERN.search(t_clean):
        return "parties"

    # 7. Business:
    if BUSINESS_PATTERN.search(t_clean):
        return "business"

    # 8. Concerts / Live Music / Singers / Bands / Tours:
    if CONCERTS_PATTERN.search(t_clean):
        return "concerts"
    # Concert Venues check
    if any(cv in v_clean for cv in ["филармони", "концертный зал", "бкз", " stadium", "ледовый дворец", "live арена", "клуб «base»", "16 тонн"]):
        if not SPORTS_PATTERN.search(t_clean) and not THEATRE_PATTERN.search(t_clean):
            return "concerts"

    # 9. Kids / Family:
    if KIDS_PATTERN.search(t_clean) or (age_restriction in ["0+", "6+"] and KIDS_PATTERN.search(d_clean)):
        if "спектакл" in t_clean or "театр" in t_clean or "балет" in t_clean or "сказк" in t_clean or "чудо" in t_clean:
            return "theatre"
        if "выставк" in t_clean or "музе" in t_clean:
            return "exhibitions"
        if "мастер-класс" in t_clean or "квест" in t_clean or "заняти" in t_clean:
            return "education"
        return "other"

    # Secondary checks in description if title was ambiguous
    if EXHIBITIONS_PATTERN.search(d_clean):
        return "exhibitions"
    if THEATRE_PATTERN.search(d_clean):
        return "theatre"
    if CONCERTS_PATTERN.search(d_clean):
        return "concerts"
    if EDUCATION_PATTERN.search(d_clean):
        return "education"
    if PARTIES_PATTERN.search(d_clean):
        return "parties"

    # --- TIER 2: SOURCE RUBRIC FALLBACK ---
    if raw_rubric:
        rubric_norm = raw_rubric.lower().strip().replace('/', ' ').replace('-', '_').replace(' ', '_')
        for key, cat_id in RUBRIC_FALLBACK_MAP.items():
            if key in rubric_norm:
                return cat_id

    # Fallback for music venues with artist-only title
    if any(cv in v_clean for cv in ["клуб", "бар", "арена", "холл", "hall"]):
        return "concerts"

    return "other"
