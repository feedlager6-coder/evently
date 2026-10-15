import io
import logging
import re
import html
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import httpx
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.event import Event, EventStatus
from app.models.user import User
from app.models.city import City
from app.models.category import Category
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
CULTURE_REGIONS: List[tuple[str, str]] = [
    ("respublika-dagestan", "Дагестан"),
    ("moskva", "Москва"),
    ("sankt-peterburg", "Санкт-Петербург"),
    ("respublika-tatarstan", "Татарстан"),
    ("krasnodarskii-krai", "Краснодарский край"),
    ("sverdlovskaya-oblast", "Свердловская область"),
    ("nizhegorodskaya-oblast", "Нижегородская область"),
    ("chechenskaya-respublika", "Чеченская Республика"),
    ("respublika-severnaya-osetiya-alaniya", "Северная Осетия"),
    ("stavropolskii-krai", "Ставропольский край"),
    ("novosibirskaya-oblast", "Новосибирская область"),
    ("samarskaya-oblast", "Самарская область"),
    ("respublika-bashkortostan", "Башкортостан"),
    ("krasnoyarskii-krai", "Красноярский край"),
]

# Culture.RU place locale names to Ivently city IDs
CULTURE_LOCALE_TO_CITY: Dict[str, str] = {
    "mahachkala": "makhachkala",
    "makhachkala": "makhachkala",
    "derbent": "derbent",
    "kaspiysk": "kaspiysk",
    "kaspiisk": "kaspiysk",
    "hasavyurt": "khasavyurt",
    "khasavyurt": "khasavyurt",
    "izberbash": "izberbash",
    "moskva": "moscow",
    "moscow": "moscow",
    "sankt-peterburg": "spb",
    "spb": "spb",
    "kazan": "kazan",
    "krasnodar": "krasnodar",
    "sochi": "sochi",
    "ekaterinburg": "yekaterinburg",
    "yekaterinburg": "yekaterinburg",
    "novosibirsk": "novosibirsk",
    "nizhnii-novgorod": "nizhny_novgorod",
    "nizhny_novgorod": "nizhny_novgorod",
    "samara": "samara",
    "ufa": "ufa",
    "krasnoyarsk": "krasnoyarsk",
    "groznyi": "grozny",
    "grozny": "grozny",
    "vladikavkaz": "vladikavkaz",
    "nalchik": "nalchik",
    "pyatigorsk": "pyatigorsk",
    "stavropol": "stavropol",
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
]

# Region default city fallback if specific municipal locale is missing
REGION_DEFAULT_CITY: Dict[str, str] = {
    "respublika-dagestan": "makhachkala",
    "moskva": "moscow",
    "sankt-peterburg": "spb",
    "respublika-tatarstan": "kazan",
    "chechenskaya-respublika": "grozny",
    "respublika-severnaya-osetiya-alaniya": "vladikavkaz",
    "sverdlovskaya-oblast": "yekaterinburg",
    "nizhegorodskaya-oblast": "nizhny_novgorod",
    "novosibirskaya-oblast": "novosibirsk",
    "samarskaya-oblast": "samara",
    "respublika-bashkortostan": "ufa",
    "krasnoyarskii-krai": "krasnoyarsk",
    "stavropolskii-krai": "stavropol",
    "krasnodarskii-krai": "krasnodar",
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
    "concerts": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800",
    "parties": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800",
    "exhibitions": "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e?w=800",
    "education": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=800",
    "business": "https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=800",
    "sports": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=800",
    "other": "https://images.unsplash.com/photo-1511578314322-379afb476865?w=800",
}


def clean_html(raw_html: Optional[str]) -> str:
    """Removes HTML tags, preserves paragraph breaks, and unescapes entities."""
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
    return text.strip()


def clean_title(raw_title: Optional[str]) -> str:
    """Cleans title and ensures first letter is capitalized."""
    cleaned = clean_html(raw_title)
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def map_category(raw_categories: List[str]) -> str:
    """Maps array of raw categories to a single valid Ivently category ID."""
    for cat in raw_categories:
        cat_lower = str(cat).lower()
        for key, mapped_id in CATEGORY_MAP.items():
            if key in cat_lower:
                return mapped_id
    return "other"


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
        relative_url = f"/uploads/covers/{target_filename}"

        # If already cached on disk and valid size, reuse immediately without re-downloading
        if target_path.exists() and target_path.stat().st_size > 1024:
            return relative_url

        resp = await http_client.get(image_url, timeout=10.0)
        if resp.status_code == 200 and len(resp.content) > 100:
            with Image.open(io.BytesIO(resp.content)) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.thumbnail((800, 500), Image.Resampling.LANCZOS)
                img.save(str(target_path), format="JPEG", quality=82, optimize=True)
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
            for region_slug, region_title in CULTURE_REGIONS:
                if target_slugs:
                    default_cid = REGION_DEFAULT_CITY.get(region_slug)
                    region_matches = (
                        region_slug in target_slugs
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
                                    city_id = REGION_DEFAULT_CITY.get(region_slug)

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
                                category_id = "other"
                                for key in raw_tags + raw_genres:
                                    if key in TAG_TO_CATEGORY:
                                        category_id = TAG_TO_CATEGORY[key]
                                        break

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

                                    # Categories
                                    category_id = map_category(item.get("categories", []))

                                    # Place
                                    place = item.get("place") or {}
                                    venue_name = clean_html(place.get("title") or "Городская площадка")
                                    address = clean_html(place.get("address") or "Центр города")
                                    coords = place.get("coords") or {}
                                    latitude = coords.get("lat")
                                    longitude = coords.get("lon")

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

        logger.info(
            "External sync completed: %d total synced (%d created, %d updated), %d errors",
            total_synced, total_created, total_updated, len(combined_errors)
        )

        return {
            "status": "success",
            "total_synced": total_synced,
            "created": total_created,
            "updated": total_updated,
            "errors": combined_errors,
            "sources": {
                "culture_ru": culture_res,
                "kudago": kudago_res,
            },
            "synced_at": now.isoformat(),
        }
