import io
import logging
import re
import html
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import httpx
try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.event import Event, EventStatus
from app.models.user import User
from app.models.city import City
from app.models.category import Category
from app.models.attendee import EventAttendee
from app.models.interest import EventInterest
from app.services.storage_service import storage_service

logger = logging.getLogger("evently.external_sync")

# City mapping from KudaGo location slugs to Ivently city IDs
KUDAGO_CITY_MAP: Dict[str, str] = {
    "msk": "moscow",
    "spb": "spb",
    "kzn": "kazan",
    "krd": "krasnodar",
    "sochi": "sochi",
    "ekb": "yekaterinburg",
    "nsk": "novosibirsk",
    "nnv": "nizhny_novgorod",
    "smr": "samara",
    "ufa": "ufa",
    "krasnoyarsk": "krasnoyarsk",
}

# Supported cultural regions for Culture.RU official afisha scraper
# Format: (culture_ru_slug, region_title, target_city_id)
CULTURE_REGIONS: List[tuple[str, str, str]] = [
    # Dagestan & North Caucasus
    ("makhachkala", "Махачкала (Дагестан)", "makhachkala"),
    ("respublika-dagestan-kaspiysk", "Каспийск", "kaspiysk"),
    ("respublika-dagestan-derbent", "Дербент", "derbent"),
    ("respublika-dagestan-hasavyurt", "Хасавюрт", "khasavyurt"),
    ("respublika-dagestan-izberbash", "Избербаш", "izberbash"),
    ("chechenskaya-respublika", "Грозный (Чечня)", "grozny"),
    ("respublika-severnaya-osetiya-alaniya", "Владикавказ (Северная Осетия)", "vladikavkaz"),
    ("kabardino-balkarskaya-respublika", "Нальчик", "nalchik"),
    ("stavropolskiy-kray-pyatigorsk", "Пятигорск", "pyatigorsk"),
    ("stavropolskiy-kray-stavropol", "Ставрополь", "stavropol"),

    # Federal Centers & Major Metros
    ("moskva", "Москва", "moscow"),
    ("sankt-peterburg", "Санкт-Петербург", "spb"),
    ("kazan", "Казань", "kazan"),

    # South & Volga
    ("krasnodar", "Краснодар", "krasnodar"),
    ("krasnodarskiy-kray-sochi", "Сочи", "sochi"),
    ("rostov-na-donu", "Ростов-на-Дону", "rostov_on_don"),
    ("volgograd", "Волгоград", "volgograd"),
    ("saratov", "Саратов", "saratov"),
    ("voronezh", "Воронеж", "voronezh"),
    ("samara", "Самара", "samara"),
    ("nizhegorodskaya-oblast", "Нижний Новгород", "nizhny_novgorod"),
    ("ufa", "Уфа", "ufa"),
    ("perm", "Пермь", "perm"),

    # Urals & Siberia
    ("sverdlovskaya-oblast", "Екатеринбург", "yekaterinburg"),
    ("chelyabinsk", "Челябинск", "chelyabinsk"),
    ("tyumen", "Тюмень", "tyumen"),
    ("omsk", "Омск", "omsk"),
    ("novosibirsk", "Новосибирск", "novosibirsk"),
    ("krasnoyarsk", "Красноярск", "krasnoyarsk"),
    ("irkutsk", "Иркутск", "irkutsk"),

    # Far East & West
    ("khabarovsk", "Хабаровск", "khabarovsk"),
    ("vladivostok", "Владивосток", "vladivostok"),
    ("kaliningradskaya-oblast", "Калининград", "kaliningrad"),
    ("yaroslavl", "Ярославль", "yaroslavl"),
]

# Culture.RU place locale names to Ivently city IDs
CULTURE_LOCALE_TO_CITY: Dict[str, str] = {
    "mahachkala": "makhachkala",
    "makhachkala": "makhachkala",
    "махачкала": "makhachkala",
    "derbent": "derbent",
    "дербент": "derbent",
    "kaspiysk": "kaspiysk",
    "kaspiisk": "kaspiysk",
    "каспийск": "kaspiysk",
    "hasavyurt": "khasavyurt",
    "khasavyurt": "khasavyurt",
    "хасавюрт": "khasavyurt",
    "izberbash": "izberbash",
    "избербаш": "izberbash",
    "moskva": "moscow",
    "moscow": "moscow",
    "москва": "moscow",
    "sankt-peterburg": "spb",
    "spb": "spb",
    "санкт-петербург": "spb",
    "петербург": "spb",
    "kazan": "kazan",
    "казань": "kazan",
    "krasnodar": "krasnodar",
    "краснодар": "krasnodar",
    "sochi": "sochi",
    "сочи": "sochi",
    "ekaterinburg": "yekaterinburg",
    "yekaterinburg": "yekaterinburg",
    "екатеринбург": "yekaterinburg",
    "novosibirsk": "novosibirsk",
    "новосибирск": "novosibirsk",
    "nizhnii-novgorod": "nizhny_novgorod",
    "nizhny_novgorod": "nizhny_novgorod",
    "нижний новгород": "nizhny_novgorod",
    "samara": "samara",
    "самара": "samara",
    "ufa": "ufa",
    "уфа": "ufa",
    "krasnoyarsk": "krasnoyarsk",
    "красноярск": "krasnoyarsk",
    "groznyi": "grozny",
    "grozny": "grozny",
    "грозный": "grozny",
    "vladikavkaz": "vladikavkaz",
    "владикавказ": "vladikavkaz",
    "nalchik": "nalchik",
    "нальчик": "nalchik",
    "pyatigorsk": "pyatigorsk",
    "пятигорск": "pyatigorsk",
    "stavropol": "stavropol",
    "ставрополь": "stavropol",
    "rostov-na-donu": "rostov_on_don",
    "rostov_on_don": "rostov_on_don",
    "ростов-на-дону": "rostov_on_don",
    "ростов": "rostov_on_don",
    "volgograd": "volgograd",
    "волгоград": "volgograd",
    "saratov": "saratov",
    "саратов": "saratov",
    "voronezh": "voronezh",
    "воронеж": "voronezh",
    "perm": "perm",
    "пермь": "perm",
    "chelyabinsk": "chelyabinsk",
    "челябинск": "chelyabinsk",
    "tyumen": "tyumen",
    "тюмень": "tyumen",
    "omsk": "omsk",
    "омск": "omsk",
    "irkutsk": "irkutsk",
    "иркутск": "irkutsk",
    "khabarovsk": "khabarovsk",
    "хабаровск": "khabarovsk",
    "vladivostok": "vladivostok",
    "владивосток": "vladivostok",
    "kaliningrad": "kaliningrad",
    "калининград": "kaliningrad",
    "yaroslavl": "yaroslavl",
    "ярославль": "yaroslavl",
}

# Fallback substrings in venue address/name for city mapping
ADDRESS_CITY_FALLBACK: List[tuple[str, str]] = [
    ("махачкал", "makhachkala"),
    ("дербент", "derbent"),
    ("каспийск", "kaspiysk"),
    ("хасавюрт", "khasavyurt"),
    ("избербаш", "izberbash"),
    ("москв", "moscow"),
    ("петербург", "spb"),
    ("питер", "spb"),
    ("казан", "kazan"),
    ("краснодар", "krasnodar"),
    ("сочи", "sochi"),
    ("екатеринбург", "yekaterinburg"),
    ("новосибирск", "novosibirsk"),
    ("нижний новгород", "nizhny_novgorod"),
    ("самара", "samara"),
    ("уфа", "ufa"),
    ("красноярск", "krasnoyarsk"),
    ("грозн", "grozny"),
    ("владикавказ", "vladikavkaz"),
    ("нальчик", "nalchik"),
    ("пятигорск", "pyatigorsk"),
    ("ставропол", "stavropol"),
    ("ростов", "rostov_on_don"),
    ("волгоград", "volgograd"),
    ("саратов", "saratov"),
    ("воронеж", "voronezh"),
    ("перм", "perm"),
    ("челябинск", "chelyabinsk"),
    ("тюмен", "tyumen"),
    ("омск", "omsk"),
    ("иркутск", "irkutsk"),
    ("хабаровск", "khabarovsk"),
    ("владивосток", "vladivostok"),
    ("калининград", "kaliningrad"),
    ("ярославл", "yaroslavl"),
]

# Region default city fallback if specific municipal locale is missing
REGION_DEFAULT_CITY: Dict[str, str] = {
    "makhachkala": "makhachkala",
    "respublika-dagestan-mahachkala": "makhachkala",
    "respublika-dagestan": "makhachkala",
    "respublika-dagestan-kaspiysk": "kaspiysk",
    "kaspiysk": "kaspiysk",
    "respublika-dagestan-derbent": "derbent",
    "derbent": "derbent",
    "respublika-dagestan-hasavyurt": "khasavyurt",
    "khasavyurt": "khasavyurt",
    "respublika-dagestan-izberbash": "izberbash",
    "izberbash": "izberbash",
    "chechenskaya-respublika": "grozny",
    "respublika-severnaya-osetiya-alaniya": "vladikavkaz",
    "kabardino-balkarskaya-respublika": "nalchik",
    "nalchik": "nalchik",
    "stavropolskiy-kray-pyatigorsk": "pyatigorsk",
    "pyatigorsk": "pyatigorsk",
    "stavropolskiy-kray-stavropol": "stavropol",
    "stavropolskiy-kray": "stavropol",
    "stavropol": "stavropol",
    "moskva": "moscow",
    "sankt-peterburg": "spb",
    "kazan": "kazan",
    "krasnodar": "krasnodar",
    "krasnodarskiy-kray-sochi": "sochi",
    "krasnodarskiy-kray": "krasnodar",
    "sochi": "sochi",
    "rostov-na-donu": "rostov_on_don",
    "volgograd": "volgograd",
    "saratov": "saratov",
    "voronezh": "voronezh",
    "samara": "samara",
    "nizhegorodskaya-oblast": "nizhny_novgorod",
    "ufa": "ufa",
    "perm": "perm",
    "sverdlovskaya-oblast": "yekaterinburg",
    "chelyabinsk": "chelyabinsk",
    "tyumen": "tyumen",
    "omsk": "omsk",
    "novosibirsk": "novosibirsk",
    "novosibirskaya-oblast": "novosibirsk",
    "krasnoyarsk": "krasnoyarsk",
    "krasnoyarskii-krai": "krasnoyarsk",
    "irkutsk": "irkutsk",
    "khabarovsk": "khabarovsk",
    "vladivostok": "vladivostok",
    "kaliningradskaya-oblast": "kaliningrad",
    "kaliningrad": "kaliningrad",
    "yaroslavl": "yaroslavl",
}

# Category mapping from external tags to Ivently category IDs
CATEGORY_MAP: Dict[str, str] = {
    "concert": "concerts",
    "music": "concerts",
    "party": "parties",
    "club": "parties",
    "dance": "parties",
    "standup": "parties",
    "comedy": "parties",
    "exhibition": "exhibitions",
    "art": "exhibitions",
    "photo": "exhibitions",
    "museum": "exhibitions",
    "education": "education",
    "lecture": "education",
    "workshop": "education",
    "masterclass": "education",
    "business": "business",
    "conference": "business",
    "meetup": "business",
    "sport": "sports",
    "sports": "sports",
    "fitness": "sports",
    "theater": "other",
    "festival": "parties",
    "tour": "other",
    "kids": "other",
}

TAG_TO_CATEGORY: Dict[str, str] = {
    "kontserty": "concerts",
    "muzyka": "concerts",
    "rok": "concerts",
    "dzhaz": "concerts",
    "klassicheskaya-muzyka": "concerts",
    "folklor": "concerts",
    "vokal": "concerts",
    "opera": "concerts",
    "pesni": "concerts",
    "vecherinki": "parties",
    "festivali": "parties",
    "shou": "parties",
    "dlya-molodezhi": "parties",
    "tantsy": "parties",
    "karnaval": "parties",
    "vystavki": "exhibitions",
    "iskusstvo": "exhibitions",
    "muzei": "exhibitions",
    "zhivopis": "exhibitions",
    "fotografiya": "exhibitions",
    "skulptura": "exhibitions",
    "galerei": "exhibitions",
    "obrazovanie": "education",
    "lektsii": "education",
    "master-klassy": "education",
    "obuchenie": "education",
    "literatura": "education",
    "knigi": "education",
    "chteniya": "education",
    "prosvetitelskie": "education",
    "biznes": "business",
    "konferentsii": "business",
    "forumy": "business",
    "sport": "sports",
    "turniry": "sports",
    "sorevnovaniya": "sports",
    "spektakli": "other",
    "teatr": "other",
    "kino": "other",
    "filmy": "other",
    "ekskursii": "other",
    "kraevedenie": "other",
}

DEFAULT_COVERS: Dict[str, str] = {
    "theatre": "https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?w=800",
    "concerts": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800",
    "parties": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800",
    "exhibitions": "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e?w=800",
    "education": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=800",
    "business": "https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=800",
    "sports": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=800",
    "other": "https://images.unsplash.com/photo-1511578314322-379afb476865?w=800",
}


def clean_html(raw_html: Optional[str]) -> str:
    """Removes HTML tags, preserves paragraph breaks, unescapes entities, and strips technical prefixes."""
    if not raw_html:
        return ""
    # Replace <br>, </p>, </div>, </li> with newlines to preserve structure
    text = re.sub(r"<(?:br|/p|/div|/li)[^>]*>", "\n\n", raw_html, flags=re.IGNORECASE)
    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # Normalize spaces within each line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Collapse multiple consecutive empty lines to maximum 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip technical HTML prefixes and BBCode tags (e.g. "[HTML]", "[/HTML]", "HTML\nВ программе...", "HTML: ...", "html - ...")
    text = re.sub(r"\[/?(?:HTML|html)\]", "", text)
    text = re.sub(r"^\s*(?:HTML|html)\s*[:\-]?\s*", "", text).strip()
    return text.strip()


def clean_title(raw_title: Optional[str]) -> str:
    """Cleans title and ensures first letter is capitalized."""
    cleaned = clean_html(raw_title)
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def resolve_category(
    raw_cat: str = "",
    title: str = "",
    description: str = "",
    venue_name: str = "",
    raw_tags: Optional[List[str]] = None,
    raw_genres: Optional[List[str]] = None,
    raw_categories: Optional[List[str]] = None,
) -> str:
    """
    Intelligently maps event to one of the 8 canonical Ivently categories:
    theatre, exhibitions, education, sports, concerts, parties, business, other.
    Uses regex with word boundaries for short roots and enforces strict hierarchy.
    """
    t_raw = (title or "").strip()
    t_low = t_raw.lower()

    extra_cats = []
    if raw_cat:
        extra_cats.append(raw_cat)
    if raw_categories:
        extra_cats.extend([str(c) for c in raw_categories if c])
    if raw_tags:
        extra_cats.extend([str(t) for t in raw_tags if t])
    if raw_genres:
        extra_cats.extend([str(g) for g in raw_genres if g])

    cats_str = " ".join(extra_cats).lower()
    venue_low = (venue_name or "").strip().lower()
    desc_sample = (description or "")[:400].strip().lower()

    primary_text = f"{t_low} {cats_str}".strip()

    def has_word(pattern: str, text: str) -> bool:
        return bool(re.search(pattern, text, re.IGNORECASE))

    # Explicit exclusions from theatre if title is explicitly an exhibition, lecture, masterclass, excursion
    is_non_theatre_title = bool(re.search(r'(?<![а-яё])(?:выставк|экспозиц|экскурси|маршрут|лекци|мастер-класс|семинар)', t_low))
    has_performance_root = bool(re.search(r'(?<![а-яё])(?:спектакл|спектал|балет|опер[аые]|мюзикл|оперетт|пьес[аы]|моноспектакл|кукол|инсценировк|фатима)', t_low))

    # 1. Спектакли и театр (theatre)
    theatre_pattern = (
        r'(?<![а-яё])(?:'
        r'спектакл|спектал|театр|балет|опер[аые]|мюзикл|оперетт|'
        r'пьес[аы]|постановк|драм[аы]|комеди[яи]|трагеди|моноспектакл|'
        r'кукол|инсценировк|сказк[аи]|фатима|гастрол|антреприз'
        r')'
    )
    if has_word(theatre_pattern, primary_text):
        if not (is_non_theatre_title and not has_performance_root):
            return "theatre"
    if has_word(r'(?<![а-яё])театр', venue_low) and not is_non_theatre_title:
        return "theatre"

    # 2. Выставки (exhibitions)
    # (если в заголовке нет слов концерт, спектакль, спекталь, лекция, мастер-класс, попурри, ансамбль, филармония)
    is_theatre_or_concert_or_edu_title = bool(re.search(
        r'(?<![а-яё])(?:концерт|симфони|оркестр|спектакл|спектал|лекци|мастер-класс|попурри|ансамбл|филармони|хор(?![а-яё])|капелл)',
        t_low
    ))
    exhibitions_pattern = (
        r'(?<![а-яё])(?:'
        r'выставк|экспозиц|вернисаж|галере|живопис|фотовыставк|'
        r'кинопоказ|кинолектори|фильм|мультипликац|музе[йяе]|экспонат'
        r')'
    )
    if has_word(exhibitions_pattern, primary_text) and not is_theatre_or_concert_or_edu_title:
        return "exhibitions"

    # 3. Образование (education)
    education_pattern = (
        r'(?<![а-яё])(?:'
        r'лекци|мастер-класс|мастер класс|семинар|урок(?![а-яё])|воркшоп|'
        r'тренинг|практикум|викторин|квиз|интеллектуальн|литературн|'
        r'чтени[яй]|книжн|библиотек|творческая встреча|круглый стол|'
        r'бесед[аы]|знакомство с|час истории|патриотическ|экологическ|'
        r'краеведческ|язык как'
        r')'
    )
    if has_word(education_pattern, primary_text):
        return "education"

    # 4. Концерты (concerts)
    concerts_pattern = (
        r'(?<![а-яё])(?:'
        r'концерт|симфони|оркестр|филармони|ансамбл|'
        r'хор(?![а-яё])|хорового|вокальн|инструментальн|фортепиан|органн|'
        r'джаз|романс|сольник|музыкальн|песн[ия]|мелоди|'
        r'попурри|сонат[аы]|сюит[аы]|кантат|увертюр|ари[яи]|'
        r'капелл|трио|квартет|квинтет|дуэт|хореограф|танц'
        r')'
    )
    if has_word(concerts_pattern, primary_text):
        return "concerts"
    if has_word(r'(?<![а-яё])(?:филармони|консерватори|ансамбл|оркестр|капелл|дом музыки|музыкальный театр)', venue_low) and not is_theatre_or_concert_or_edu_title:
        return "concerts"

    # 5. Спорт и активный отдых (sports)
    # ТОЛЬКО по целым словам/корням через regex (?<![а-яё]):
    # ЗАПРЕЩЕНО использовать голый корень "тур" без границы слова,
    # чтобы слова «культура» и «литература» НИКОГДА не попадали в sports!
    sports_pattern = (
        r'(?<![а-яё])(?:'
        r'экскурси|пешеходн|маршрут|поход(?![а-яё])|квест(?![а-яё])|'
        r'спорт|забег|матч(?![а-яё])|турнир|чемпионат|соревнован|'
        r'спартакиад|фитнес|йог[аи]|зарядк|велопробег|туристическ|туризм'
        r')'
    )
    if has_word(sports_pattern, primary_text):
        return "sports"

    # 6. Вечеринки и шоу (parties)
    parties_pattern = (
        r'(?<![а-яё])(?:'
        r'вечеринк|стендап|standup|шоу(?![а-яё])|дискотек|фестивал|'
        r'праздник|гуляни|конкурс|карнавал|бал(?![а-яё])|огонек|юбилейн'
        r')'
    )
    if has_word(parties_pattern, primary_text):
        return "parties"

    # 7. Бизнес (business)
    business_pattern = (
        r'(?<![а-яё])(?:'
        r'бизнес|форум(?![а-яё])|конференци|стартап|предпринимател|'
        r'нетворкинг|маркетинг|инвестиц'
        r')'
    )
    if has_word(business_pattern, primary_text):
        return "business"

    # 8. Вторичная проверка по venue_name + description (первые 300 символов)
    secondary_text = f"{venue_low} {desc_sample[:300]}".strip()
    if secondary_text:
        # theatre: спектакл, спектал, театр, режиссер, актер, сцен
        if has_word(r'(?<![а-яё])(?:спектакл|спектал|театр|режиссер|актер|сцен)', secondary_text) and not is_non_theatre_title:
            return "theatre"
        # education: библиотек, лекци, учащихся, школьник, мастер-класс, истори, литератур
        if has_word(r'(?<![а-яё])(?:библиотек|лекци|учащихся|школьник|мастер-класс|истори|литератур)', secondary_text):
            return "education"
        # concerts: MUST BE BEFORE exhibitions!
        # concerts: концерт, песн, музык, филармони, ансамбл, капелл, оркестр, симфони, попурри, хор, танц
        if has_word(r'(?<![а-яё])(?:концерт|песн|музык|филармони|ансамбл|капелл|оркестр|симфони|попурри|хор(?![а-яё])|танц)', secondary_text):
            return "concerts"
        # exhibitions: выставк, экспонат, музе, экспозиц, вернисаж, фотовыставк, живопис, скульптур, галере
        if has_word(r'(?<![а-яё])(?:выставк|экспонат|музе[йяе]|экспозиц|вернисаж|фотовыставк|живопис|скульптур|галере)', secondary_text):
            return "exhibitions"
        # sports: экскурси, маршрут, спорт, соревнован
        if has_word(r'(?<![а-яё])(?:экскурси|маршрут|спорт|соревнован)', secondary_text):
            return "sports"
        # parties: праздник, фестивал, шоу
        if has_word(r'(?<![а-яё])(?:праздник|фестивал|шоу(?![а-яё]))', secondary_text):
            return "parties"

    return "other"


def map_category(raw_categories: List[str]) -> str:
    """Fallback legacy category mapper."""
    return resolve_category(raw_categories=raw_categories)


def parse_price(price_raw: Any, is_free: bool = False) -> Optional[float]:
    """Extracts first valid number from price string or returns 0.0 if free."""
    if is_free:
        return 0.0
    if price_raw is None:
        return None
    if isinstance(price_raw, (int, float)):
        return float(price_raw)
    price_str = str(price_raw).lower()
    if "бесплатно" in price_str or "свободный" in price_str:
        return 0.0
    nums = re.findall(r"\d+", price_str.replace(" ", "").replace("\xa0", ""))
    if nums:
        return float(nums[0])
    return None


def append_partner_utm(url: Optional[str]) -> Optional[str]:
    """Appends partner tracking parameters to ticket purchase link."""
    if not url:
        return None
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        return None
    sep = "&" if "?" in clean_url else "?"
    if "utm_source" not in clean_url:
        clean_url = f"{clean_url}{sep}utm_source=ivently&utm_medium=referral&utm_campaign=afisha"
    return clean_url


async def download_and_cache_cover(
    http_client: httpx.AsyncClient,
    image_url: Optional[str],
    ext_id: str,
) -> Optional[str]:
    """
    Downloads external image on Russian server, resizes to max 800x500 maintaining aspect ratio,
    optimizes as JPEG quality=82 (~50 KB), and saves to local uploads/covers/ext_{ext_id}.jpg.
    Returns relative URL path '/uploads/covers/ext_{ext_id}.jpg' for fast delivery through VPN.
    """
    if not image_url or not image_url.startswith("http"):
        return None

    try:
        local_covers_dir = storage_service.get_local_storage_dir() / "covers"
        local_covers_dir.mkdir(parents=True, exist_ok=True)
        target_filename = f"ext_{ext_id}.jpg"
        target_path = local_covers_dir / target_filename
        thumb_filename = f"ext_{ext_id}_thumb.jpg"
        thumb_path = local_covers_dir / thumb_filename
        relative_url = f"/uploads/covers/{target_filename}"

        # If already cached on disk and valid size, ensure thumbnail exists and return
        if target_path.exists() and target_path.stat().st_size > 1024:
            if not thumb_path.exists() or thumb_path.stat().st_size < 100:
                try:
                    if Image and ImageOps:
                        with Image.open(str(target_path)) as img:
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            thumb_img = ImageOps.fit(img, (160, 160), Image.Resampling.LANCZOS)
                            thumb_img.save(str(thumb_path), format="JPEG", quality=78, optimize=True, progressive=False)
                except Exception as e:
                    logger.warning("Failed to generate thumb from cached cover ext_%s: %s", ext_id, e)
            return relative_url

        resp = await http_client.get(image_url, timeout=10.0)
        if resp.status_code == 200 and len(resp.content) > 100:
            if Image is None:
                target_path.write_bytes(resp.content)
                return relative_url
            with Image.open(io.BytesIO(resp.content)) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                # Main cover: max 800x500
                cover_img = img.copy()
                cover_img.thumbnail((800, 500), Image.Resampling.LANCZOS)
                cover_img.save(str(target_path), format="JPEG", quality=82, optimize=True)

                # Square thumbnail: strictly 160x160 px for Telegram Bot API inline popup
                if ImageOps:
                    thumb_img = ImageOps.fit(img, (160, 160), Image.Resampling.LANCZOS)
                else:
                    thumb_img = img.copy()
                    thumb_img.thumbnail((160, 160), Image.Resampling.LANCZOS)
                thumb_img.save(str(thumb_path), format="JPEG", quality=78, optimize=True, progressive=False)
            return relative_url
    except Exception as e:
        logger.warning("Failed to cache cover for ext_id %s from %s: %s", ext_id, image_url, e)

    return image_url


class ExternalSyncService:
    """
    Automated network importer for 100% authentic live events across Russian cities.
    Sources:
      1. Portal «Культура.РФ» (National culture portal, primary live feed across Russia)
      2. KudaGo Public API (where reachable)
    Zero mock events: genuine descriptions, local high-speed cover caching, direct ticket links.
    Idempotent: updates existing events by (source_name, external_id) without creating duplicates.
    Resilient: uses database savepoints so individual parsing errors never roll back entire transaction.
    """

    @classmethod
    async def get_curator_user_id(
        cls,
        session: AsyncSession,
        admin_user_id: Optional[int] = None
    ) -> int:
        """
        Resolves or creates a guaranteed system curator user for external ingested events.
        """
        if admin_user_id:
            admin_user = await session.get(User, admin_user_id)
            if admin_user:
                return admin_user.id

        curator_tg_id = 777000
        stmt = select(User).where(User.telegram_id == curator_tg_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user:
            return user.id

        # Check existing ivently_curator by username
        stmt_username = select(User).where(User.username == "ivently_curator")
        user_by_name = (await session.execute(stmt_username)).scalar_one_or_none()
        if user_by_name:
            return user_by_name.id

        # Fallback to any existing user
        any_user = (await session.execute(select(User).limit(1))).scalar_one_or_none()
        if any_user:
            return any_user.id

        # Create system curator user
        curator = User(
            telegram_id=curator_tg_id,
            username="ivently_curator",
            first_name="Афиша Ivently",
            last_name="",
            default_city_id="makhachkala"
        )
        session.add(curator)
        await session.commit()
        await session.refresh(curator)
        return curator.id

    @classmethod
    async def sync_culture_ru_events(
        cls,
        session: AsyncSession,
        curator_user_id: int,
        target_slugs: Optional[List[str]] = None,
        max_events_per_region: int = 20,
    ) -> Dict[str, Any]:
        """
        Fetches authentic live events from Portal «Культура.РФ» across all Russian regions.
        Zero mock data: real titles, local cached CDN covers, official venue locations, dates,
        full parsed descriptions, and direct ticketing cashier links (saleLink).
        """
        now = datetime.now(timezone.utc)
        total_synced = 0
        total_created = 0
        total_updated = 0
        errors = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Cache active city IDs to ensure foreign key safety
        active_cities_res = await session.execute(select(City.id).where(City.is_active == True))
        active_city_ids = set(active_cities_res.scalars().all())

        detail_semaphore = asyncio.Semaphore(8)

        async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
            for region_slug, region_title, target_city_id in CULTURE_REGIONS:
                if target_slugs:
                    default_cid = target_city_id or REGION_DEFAULT_CITY.get(region_slug)
                    region_matches = (
                        region_slug in target_slugs
                        or (target_city_id and target_city_id in target_slugs)
                        or (default_cid and default_cid in target_slugs)
                    )
                    if not region_matches:
                        continue

                url = f"https://www.culture.ru/afisha/{region_slug}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning("Culture.RU region %s returned status %s", region_slug, resp.status_code)
                        continue

                    # Extract Next.js data payload
                    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                    if not match:
                        logger.warning("Culture.RU region %s: __NEXT_DATA__ script not found", region_slug)
                        continue

                    payload = json.loads(match.group(1))
                    events_block = payload.get("props", {}).get("pageProps", {}).get("events", {})
                    items = events_block.get("items", [])
                    if not items:
                        continue

                    selected_items = items[:max_events_per_region]

                    # Parallel worker for fetching detailed event page (text and saleLink)
                    async def fetch_item_details(item_data: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
                        raw_i = item_data.get("_id") or item_data.get("id")
                        if not raw_i:
                            return None, None
                        clean_i = str(raw_i).split("_")[0]
                        slug_i = item_data.get("name") or ""
                        page_u = f"https://www.culture.ru/events/{clean_i}/{slug_i}"

                        async with detail_semaphore:
                            try:
                                d_res = await client.get(page_u, timeout=8.0)
                                if d_res.status_code == 200:
                                    dm = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', d_res.text, re.DOTALL)
                                    if dm:
                                        d_data = json.loads(dm.group(1))
                                        ev = d_data.get("props", {}).get("pageProps", {}).get("event", {})
                                        raw_t = ev.get("text") or ""
                                        d_desc = clean_html(raw_t)
                                        s_link = ev.get("saleLink")
                                        if isinstance(s_link, str) and s_link.strip().startswith("http"):
                                            s_link = s_link.strip()
                                        else:
                                            s_link = None
                                        return (d_desc if len(d_desc) > 20 else None), s_link
                            except Exception as e:
                                logger.debug("Detail fetch error for %s: %s", clean_i, e)
                        return None, None

                    # Concurrently fetch details for all items in this region
                    details_results = await asyncio.gather(*(fetch_item_details(it) for it in selected_items))

                    for item, (detail_desc, detail_sale_link) in zip(selected_items, details_results):
                        try:
                            async with session.begin_nested():
                                raw_id = item.get("_id") or item.get("id")
                                if not raw_id:
                                    continue

                                # Clean single ID without duplicates (fix for 404 links)
                                clean_id = str(raw_id).split("_")[0]
                                ext_id = f"cul_{clean_id}"
                                slug_name = item.get("name") or ""
                                official_culture_url = f"https://www.culture.ru/events/{clean_id}/{slug_name}"

                                title = clean_title(item.get("title") or item.get("name"))
                                if not title:
                                    continue

                                # 1. Date & Time
                                card_sched = item.get("cardSchedule") or {}
                                primary_date = card_sched.get("primaryDate") or item.get("seanceEndDate") or item.get("date")
                                start_at = None
                                if primary_date:
                                    try:
                                        start_at = datetime.fromisoformat(str(primary_date).replace("Z", "+00:00"))
                                    except Exception:
                                        pass

                                # Filter out stale past events (more than 12h in the past)
                                if not start_at or start_at < now - timedelta(hours=12):
                                    continue

                                # 2. Venue & Address
                                places = item.get("places") or []
                                p0 = places[0] if (places and isinstance(places, list)) else {}
                                venue_name = clean_html(p0.get("title") or item.get("topPlaceTitle") or "Культурная площадка")
                                address = clean_html(p0.get("address") or "Центр города")

                                # 3. City resolution
                                loc_info = p0.get("locale") or {}
                                locale_name = str(loc_info.get("name") or "").lower().strip()
                                city_id = CULTURE_LOCALE_TO_CITY.get(locale_name)

                                if not city_id and address:
                                    addr_lower = address.lower()
                                    venue_lower = venue_name.lower()
                                    for needle, cid in ADDRESS_CITY_FALLBACK:
                                        if needle in addr_lower or needle in venue_lower:
                                            city_id = cid
                                            break

                                if not city_id:
                                    city_id = target_city_id or REGION_DEFAULT_CITY.get(region_slug)

                                # Dedicated municipal/regional routes guarantee correct city assignment
                                if target_city_id and (
                                    not city_id
                                    or city_id not in active_city_ids
                                    or target_city_id in ("sochi", "pyatigorsk", "kaspiysk", "khasavyurt", "derbent", "izberbash", "nalchik", "kaliningrad", "stavropol")
                                ):
                                    city_id = target_city_id

                                if not city_id or city_id not in active_city_ids:
                                    continue

                                if target_slugs and city_id not in target_slugs:
                                    continue

                                # 4. Coordinates
                                latitude = None
                                longitude = None
                                geo_info = p0.get("geo") or {}
                                if isinstance(geo_info, dict) and geo_info.get("latitude") and geo_info.get("longitude"):
                                    try:
                                        latitude = float(geo_info["latitude"])
                                        longitude = float(geo_info["longitude"])
                                    except (ValueError, TypeError):
                                        pass

                                # 5. Category resolution
                                raw_tags = [t.get("name", "").lower() for t in item.get("tags", []) if isinstance(t, dict)]
                                raw_genres = [g.get("name", "").lower() for g in item.get("genres", []) if isinstance(g, dict)]
                                raw_cats = [c.get("name", "").lower() for c in item.get("categories", []) if isinstance(c, dict)]
                                category_id = resolve_category(
                                    raw_cat=" ".join(raw_cats),
                                    title=title,
                                    description=detail_desc or item.get("description") or "",
                                    venue_name=venue_name,
                                    raw_tags=raw_tags,
                                    raw_genres=raw_genres,
                                    raw_categories=raw_cats,
                                )

                                # 6. Price
                                price_info = item.get("price") or {}
                                price_amount = None
                                if isinstance(price_info, dict) and price_info.get("min") is not None:
                                    price_amount = float(price_info["min"])

                                md = item.get("microdata")
                                if isinstance(md, str):
                                    try:
                                        md = json.loads(md)
                                    except Exception:
                                        md = {}
                                elif not isinstance(md, dict):
                                    md = {}

                                if price_amount is None and md.get("offers"):
                                    try:
                                        offers = md["offers"]
                                        if isinstance(offers, dict) and "price" in offers:
                                            price_amount = float(offers["price"])
                                    except (ValueError, TypeError):
                                        pass

                                if any(t.get("name") == "besplatno" for t in item.get("tags", []) if isinstance(t, dict)):
                                    price_amount = 0.0

                                # 7. Cover Image: download and cache locally for instant VPN loading
                                remote_cover_url = None
                                if md.get("image") and isinstance(md["image"], dict) and md["image"].get("url"):
                                    remote_cover_url = md["image"]["url"]

                                if not remote_cover_url and item.get("thumbnailFile"):
                                    pub_id = item["thumbnailFile"].get("publicId")
                                    if pub_id:
                                        remote_cover_url = f"https://cdn.culture.ru/images/{pub_id}"

                                if not remote_cover_url:
                                    remote_cover_url = DEFAULT_COVERS.get(category_id, DEFAULT_COVERS["other"])

                                # Cache cover locally on Russian server
                                cover_image_url = await download_and_cache_cover(
                                    http_client=client,
                                    image_url=remote_cover_url,
                                    ext_id=ext_id,
                                ) or remote_cover_url

                                # 8. Source URL: prioritize direct cashier link (saleLink), fallback to clean official page
                                raw_source_url = detail_sale_link or official_culture_url
                                source_url = append_partner_utm(raw_source_url)

                                # 9. Full Authentic Description (from page text)
                                if detail_desc:
                                    description = detail_desc
                                else:
                                    tag_titles = [t.get("title") for t in item.get("tags", []) if isinstance(t, dict) and t.get("title")]
                                    tags_part = f" Тематика: {', '.join(tag_titles[:4])}." if tag_titles else ""
                                    pushkin_part = " Доступно по Пушкинской карте." if item.get("isPushkinsCard") else ""
                                    age_part = f" Возрастное ограничение: {item.get('ageRestriction')}." if item.get("ageRestriction") else ""
                                    description = (
                                        f"Официальное культурное событие «{title}». Площадка: {venue_name} ({address})."
                                        f"{tags_part}{pushkin_part}{age_part} "
                                        f"Билеты, расписание сеансов и официальные анонсы доступны на портале «Культура.РФ»."
                                    )

                                if len(description) > 3000:
                                    description = description[:2997] + "..."

                                # 10. Idempotent Upsert (matches ext_id or previous raw_id)
                                existing_stmt = select(Event).where(
                                    Event.source_name == "culture_ru",
                                    Event.external_id.in_([ext_id, f"cul_{raw_id}"])
                                )
                                existing_event = (await session.execute(existing_stmt)).scalar_one_or_none()

                                if existing_event:
                                    existing_event.external_id = ext_id
                                    existing_event.title = title
                                    existing_event.description = description
                                    existing_event.cover_image_url = cover_image_url
                                    existing_event.category_id = category_id
                                    existing_event.city_id = city_id
                                    existing_event.start_at = start_at
                                    existing_event.venue_name = venue_name
                                    existing_event.address = address
                                    if latitude and longitude:
                                        existing_event.latitude = latitude
                                        existing_event.longitude = longitude
                                    existing_event.price_amount = price_amount
                                    existing_event.price_currency = "RUB"
                                    existing_event.source_url = source_url
                                    existing_event.last_synced_at = now
                                    existing_event.status = EventStatus.PUBLISHED.value
                                    total_updated += 1
                                else:
                                    new_event = Event(
                                        title=title,
                                        description=description,
                                        cover_image_url=cover_image_url,
                                        category_id=category_id,
                                        city_id=city_id,
                                        start_at=start_at,
                                        venue_name=venue_name,
                                        address=address,
                                        latitude=latitude,
                                        longitude=longitude,
                                        price_amount=price_amount,
                                        price_currency="RUB",
                                        status=EventStatus.PUBLISHED.value,
                                        organizer_user_id=curator_user_id,
                                        source_type="external",
                                        source_name="culture_ru",
                                        external_id=ext_id,
                                        source_url=source_url,
                                        last_synced_at=now,
                                        created_at=now,
                                        updated_at=now,
                                    )
                                    session.add(new_event)
                                    total_created += 1

                                total_synced += 1
                            await session.commit()
                        except Exception as item_err:
                            logger.warning("Error importing Culture.RU event %s: %s", item.get("_id"), item_err)
                            errors.append(f"{item.get('_id')}: {str(item_err)}")
                except Exception as reg_err:
                    logger.warning("Error fetching Culture.RU region %s: %s", region_slug, reg_err)
                    errors.append(f"{region_slug}: {str(reg_err)}")

        return {
            "source": "culture_ru",
            "total_synced": total_synced,
            "created": total_created,
            "updated": total_updated,
            "errors": errors,
        }

    @classmethod
    async def sync_kudago_events(
        cls,
        session: AsyncSession,
        curator_user_id: int,
        target_slugs: Optional[List[str]] = None,
        max_events_per_city: int = 15,
    ) -> Dict[str, Any]:
        """
        Fetches events from KudaGo API where accessible.
        Gracefully handles 403 / network timeouts without halting execution.
        """
        now = datetime.now(timezone.utc)
        now_unix = int(now.timestamp())
        total_synced = 0
        total_created = 0
        total_updated = 0
        errors = []

        kudago_slugs = list(KUDAGO_CITY_MAP.keys())
        if target_slugs:
            kudago_slugs = [s for s in kudago_slugs if s in target_slugs or KUDAGO_CITY_MAP.get(s) in target_slugs]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }

        async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
            for slug in kudago_slugs:
                ivently_city_id = KUDAGO_CITY_MAP.get(slug, slug)
                city_exists = (await session.execute(select(City.id).where(City.id == ivently_city_id))).scalar_one_or_none()
                if not city_exists:
                    continue

                url = (
                    f"https://kudago.com/public-api/v1.4/events/?"
                    f"actual_since={now_unix}&"
                    f"fields=id,title,description,body_text,dates,place,images,price,is_free,categories,site_url&"
                    f"expand=place&"
                    f"location={slug}&"
                    f"page_size={max_events_per_city}"
                )

                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])

                        for item in results:
                            try:
                                async with session.begin_nested():
                                    ext_id = str(item.get("id"))
                                    title = clean_title(item.get("title", ""))
                                    if not title:
                                        continue

                                    # Dates
                                    dates = item.get("dates", [])
                                    start_at = None
                                    if dates and isinstance(dates, list):
                                        for d in dates:
                                            s_ts = d.get("start")
                                            if s_ts and isinstance(s_ts, (int, float)):
                                                if now_unix <= s_ts <= now_unix + 90 * 86400:
                                                    start_at = datetime.fromtimestamp(s_ts, tz=timezone.utc)
                                                    break

                                    if not start_at:
                                        continue

                                    # Description
                                    body = clean_html(item.get("body_text") or item.get("description") or "")
                                    description = body if body else f"Мероприятие «{title}» в городе {ivently_city_id.capitalize()}."
                                    if len(description) > 3000:
                                        description = description[:2997] + "..."

                                    # Place
                                    place = item.get("place") or {}
                                    venue_name = clean_html(place.get("title") or "Городская площадка")
                                    address = clean_html(place.get("address") or "Центр города")
                                    coords = place.get("coords") or {}
                                    latitude = coords.get("lat")
                                    longitude = coords.get("lon")

                                    # Categories
                                    kudago_cats = item.get("categories", [])
                                    category_id = resolve_category(
                                        raw_cat=" ".join(kudago_cats),
                                        title=title,
                                        description=description,
                                        venue_name=venue_name,
                                        raw_categories=kudago_cats,
                                    )

                                    # Cover
                                    images = item.get("images", [])
                                    remote_cover = None
                                    if images and isinstance(images, list) and images[0].get("image"):
                                        remote_cover = images[0]["image"]
                                    if not remote_cover:
                                        remote_cover = DEFAULT_COVERS.get(category_id, DEFAULT_COVERS["other"])

                                    cover_image_url = await download_and_cache_cover(
                                        http_client=client,
                                        image_url=remote_cover,
                                        ext_id=f"kudago_{ext_id}",
                                    ) or remote_cover

                                    # Price
                                    is_free = bool(item.get("is_free", False))
                                    price_amount = parse_price(item.get("price"), is_free=is_free)
                                    ticket_url = append_partner_utm(item.get("site_url"))

                                    # Upsert
                                    existing_stmt = select(Event).where(
                                        Event.source_name == "kudago",
                                        Event.external_id == ext_id
                                    )
                                    existing_event = (await session.execute(existing_stmt)).scalar_one_or_none()

                                    if existing_event:
                                        existing_event.title = title
                                        existing_event.description = description
                                        existing_event.cover_image_url = cover_image_url
                                        existing_event.category_id = category_id
                                        existing_event.city_id = ivently_city_id
                                        existing_event.start_at = start_at
                                        existing_event.venue_name = venue_name
                                        existing_event.address = address
                                        if latitude and longitude:
                                            existing_event.latitude = float(latitude)
                                            existing_event.longitude = float(longitude)
                                        existing_event.price_amount = price_amount
                                        existing_event.source_url = ticket_url
                                        existing_event.last_synced_at = now
                                        existing_event.status = EventStatus.PUBLISHED.value
                                        total_updated += 1
                                    else:
                                        new_event = Event(
                                            title=title,
                                            description=description,
                                            cover_image_url=cover_image_url,
                                            category_id=category_id,
                                            city_id=ivently_city_id,
                                            start_at=start_at,
                                            venue_name=venue_name,
                                            address=address,
                                            latitude=float(latitude) if latitude else None,
                                            longitude=float(longitude) if longitude else None,
                                            price_amount=price_amount,
                                            price_currency="RUB",
                                            status=EventStatus.PUBLISHED.value,
                                            organizer_user_id=curator_user_id,
                                            source_type="external",
                                            source_name="kudago",
                                            external_id=ext_id,
                                            source_url=ticket_url,
                                            last_synced_at=now,
                                            created_at=now,
                                            updated_at=now,
                                        )
                                        session.add(new_event)
                                        total_created += 1

                                    total_synced += 1
                                await session.commit()
                            except Exception as item_err:
                                logger.warning("Error processing KudaGo item %s: %s", item.get("id"), item_err)
                    else:
                        logger.info("KudaGo API responded with status %s for %s", resp.status_code, slug)
                except Exception as e:
                    logger.warning("KudaGo fetch skipped for %s: %s", slug, e)
                    errors.append(f"{slug}: {str(e)}")

        return {
            "source": "kudago",
            "total_synced": total_synced,
            "created": total_created,
            "updated": total_updated,
            "errors": errors,
        }

    @classmethod
    async def sync_external_events(
        cls,
        session: AsyncSession,
        admin_user_id: Optional[int] = None,
        city_slugs: Optional[List[str]] = None,
        max_events_per_city: int = 20,
    ) -> Dict[str, Any]:
        """
        Master orchestrator for external event synchronization.
        Fetches 100% authentic live network events from:
          1. Portal «Культура.РФ» (National culture portal, primary live feed across Russia)
          2. KudaGo API (secondary where accessible)
        Zero hardcoded mock events. Strict idempotency.
        """
        now = datetime.now(timezone.utc)
        curator_user_id = await cls.get_curator_user_id(session, admin_user_id=admin_user_id)
        target_slugs = [s.lower().strip() for s in city_slugs] if city_slugs else None

        # 1. Primary Live Network Source: Portal «Культура.РФ»
        culture_res = await cls.sync_culture_ru_events(
            session=session,
            curator_user_id=curator_user_id,
            target_slugs=target_slugs,
            max_events_per_region=max_events_per_city,
        )

        # 2. Secondary Network Source: KudaGo API
        kudago_res = await cls.sync_kudago_events(
            session=session,
            curator_user_id=curator_user_id,
            target_slugs=target_slugs,
            max_events_per_city=max_events_per_city,
        )

        total_synced = culture_res["total_synced"] + kudago_res["total_synced"]
        total_created = culture_res["created"] + kudago_res["created"]
        total_updated = culture_res["updated"] + kudago_res["updated"]
        combined_errors = culture_res["errors"] + kudago_res["errors"]

        # 3. Auto-clean expired external events older than 3 days
        cleaned_count = 0
        try:
            cleaned_count = await cls.cleanup_expired_external_events(session=session, retention_days=3)
        except Exception as e:
            logger.warning("Auto-cleanup of expired external events failed: %s", e)

        logger.info(
            "External sync completed: %d total synced (%d created, %d updated), %d cleaned, %d errors",
            total_synced, total_created, total_updated, cleaned_count, len(combined_errors)
        )

        return {
            "status": "success",
            "total_synced": total_synced,
            "created": total_created,
            "updated": total_updated,
            "cleaned": cleaned_count,
            "errors": combined_errors,
            "sources": {
                "culture_ru": culture_res,
                "kudago": kudago_res,
            },
            "synced_at": now.isoformat(),
        }

    @classmethod
    async def cleanup_expired_external_events(
        cls,
        session: AsyncSession,
        retention_days: int = 3,
    ) -> int:
        """
        Cleans up expired external events older than retention_days (default 3 days ago)
        that have no attendees and no bookmarks, deleting their cached covers from disk.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt = (
            select(Event)
            .where(
                Event.source_type == "external",
                Event.start_at < cutoff,
                ~Event.id.in_(select(EventAttendee.event_id)),
                ~Event.id.in_(select(EventInterest.event_id)),
            )
        )
        res = await session.execute(stmt)
        expired_events = res.scalars().all()
        deleted_count = 0
        local_covers_dir = storage_service.get_local_storage_dir() / "covers"

        for event in expired_events:
            # Clean cover file if local
            if event.cover_image_url and "/uploads/covers/ext_" in event.cover_image_url:
                filename = event.cover_image_url.split("/uploads/covers/")[-1]
                file_path = local_covers_dir / filename
                try:
                    if file_path.exists():
                        file_path.unlink()
                except Exception as e:
                    logger.warning("Failed to delete expired cover %s: %s", file_path, e)
            await session.delete(event)
            deleted_count += 1

        if deleted_count > 0:
            await session.commit()
            logger.info("Auto-cleaned %d expired external events and their cached covers", deleted_count)

        return deleted_count

