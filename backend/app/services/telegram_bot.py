import html
import logging
import httpx
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.config import settings
from app.models.city import City
from app.services.parser_service import parse_query, ParsedQuery
from app.services.event_service import list_published_events
from app.schemas.event import EventSummary

logger = logging.getLogger("evently.telegram")


def resolve_absolute_image_url(url: Optional[str]) -> str:
    """Ensures thumbnail URLs sent to Telegram Bot API are valid absolute HTTP/HTTPS URLs."""
    fallback = "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=800&h=500&auto=format&fit=crop&q=85"
    if not url or not url.strip():
        return fallback
    clean = url.strip()
    if clean.startswith("http://") or clean.startswith("https://"):
        return clean
    public_host = settings.effective_public_host
    if public_host and clean.startswith("/"):
        return f"{public_host}{clean}"
    return fallback


def optimize_preview_image_url(url: Optional[str], is_thumbnail: bool = False) -> str:
    """
    Standardizes image URLs for Telegram inline previews and photo messages.
    Prevents excessively tall vertical previews by enforcing controlled landscape aspect ratios (16:10)
    for Unsplash assets, and 1:1 square for popup thumbnails.
    """
    resolved = resolve_absolute_image_url(url)
    if "images.unsplash.com" in resolved:
        base = resolved.split("?")[0]
        if is_thumbnail:
            return f"{base}?w=400&h=400&auto=format&fit=crop&q=80"
        return f"{base}?w=800&h=500&auto=format&fit=crop&q=85"
    return resolved


def format_event_price_line(event: Any) -> Optional[str]:
    """Formats event price strictly in Russian with ruble symbol (₽), strictly never RUB."""
    raw_amount = getattr(event, "price_amount", None)
    price_amount = raw_amount if isinstance(raw_amount, (int, float)) and not isinstance(raw_amount, bool) else None
    raw_is_free = getattr(event, "is_free", None)
    is_free = (raw_is_free is True) or (price_amount is not None and price_amount == 0)
    if is_free:
        return "🎟 Вход бесплатный"
    elif price_amount is not None and price_amount > 0:
        p_val = int(price_amount) if float(price_amount).is_integer() else price_amount
        return f"🎟 Вход: {p_val} ₽"
    return None


def format_event_date_str(event: Any) -> str:
    """Formats event date in Russian format '%d.%m.%Y в %H:%M'."""
    raw_start = getattr(event, "start_at", None)
    if hasattr(raw_start, "strftime") and callable(getattr(raw_start, "strftime")):
        try:
            res = raw_start.strftime("%d.%m.%Y в %H:%M")
            if isinstance(res, str):
                return res
        except Exception:
            pass
    return "Дата уточняется"


def format_event_venue_str(event: Any) -> str:
    """Formats venue and city cleanly."""
    raw_venue = getattr(event, "venue_name", None)
    venue_str = str(raw_venue).strip() if isinstance(raw_venue, str) and raw_venue.strip() else "Локация в приложении"
    raw_city = getattr(event, "city_name", None) or getattr(event, "city_id", None)
    city_str = str(raw_city).strip() if isinstance(raw_city, str) and raw_city.strip() else ""
    if city_str and city_str.lower() not in venue_str.lower():
        return f"{venue_str}, {city_str}"
    return venue_str


def format_event_card_caption(event: Any) -> str:
    """
    Formats standardized event card caption for both Share V2 and Inline Search cards.
    Output:
    🎟 <b>{title}</b>

    📅 {date_str}
    📍 {venue_display}
    {price_line}
    """
    raw_title = getattr(event, "title", "Мероприятие")
    title_str = str(raw_title).strip() if isinstance(raw_title, str) and raw_title.strip() else "Мероприятие"

    parts = [
        f"🎟 <b>{html.escape(title_str)}</b>\n",
        f"📅 {format_event_date_str(event)}",
        f"📍 {html.escape(format_event_venue_str(event))}",
    ]
    price_line = format_event_price_line(event)
    if price_line:
        parts.append(price_line)
    return "\n".join(parts)


def format_event_message(event: EventSummary) -> str:
    """Legacy alias redirecting to unified card caption."""
    return format_event_card_caption(event)


def build_mini_app_button(
    text: str,
    start_param: Optional[str] = None,
    style: Optional[str] = None
) -> Dict[str, Any]:
    """
    Builds compliant button for private bot messages.
    Supports official Telegram Bot API 'style' parameter ('primary', 'success', 'danger').
    Priority 1: If effective_public_host is available (e.g. HTTPS), use 'web_app' button.
    Priority 2: If a t.me link is configured, use 'url'.
    """
    btn: Dict[str, Any] = {"text": text}
    if style:
        btn["style"] = style

    public_host = settings.effective_public_host
    if public_host and public_host.startswith("https://"):
        target_url = f"{public_host.rstrip('/')}/"
        if start_param:
            target_url = f"{target_url}?startapp={start_param}"
        btn["web_app"] = {"url": target_url}
        return btn

    base_url = settings.effective_mini_app_url
    if base_url.startswith("https://t.me/"):
        if start_param:
            sep = "&" if "?" in base_url else "?"
            btn["url"] = f"{base_url}{sep}startapp={start_param}"
            return btn
        btn["url"] = base_url
        return btn

    if start_param:
        target_url = f"{base_url.rstrip('/')}/?startapp={start_param}"
    else:
        target_url = base_url
    btn["web_app"] = {"url": target_url}
    return btn


def build_event_inline_keyboard(event_id: str) -> Dict[str, Any]:
    """
    Constructs compliant inline keyboard with official button 'Открыть событие 🧭'.
    Uses direct 'url' button for Telegram inline compatibility across all chats.
    """
    clean_id = str(event_id).replace("event_", "").strip()
    url = settings.get_event_deep_link(clean_id)
    return {
        "inline_keyboard": [
            [
                {"text": "Открыть событие 🧭", "url": url}
            ]
        ]
    }


def build_catalog_inline_keyboard() -> Dict[str, Any]:
    """
    Constructs compliant inline keyboard for inline query empty state.
    Uses direct 'url' button for Telegram inline query compatibility in all chat types.
    """
    mini_app_url = settings.effective_mini_app_url
    return {
        "inline_keyboard": [
            [
                {"text": "🧭 Открыть Ivently Mini App", "url": mini_app_url}
            ]
        ]
    }


async def check_public_image_validity(url: Optional[str]) -> bool:
    """
    Checks if an image URL is publicly reachable over HTTPS with a valid image Content-Type.
    Uses non-blocking HEAD request with short timeout (1.5s).
    Does NOT download or transcode images.
    """
    if not url or not isinstance(url, str):
        return False
    clean = url.strip()
    if not clean.startswith("https://"):
        return False
    try:
        async with httpx.AsyncClient(timeout=1.5, follow_redirects=True) as client:
            resp = await client.head(clean)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "").lower()
                if "image/jpeg" in ct or "image/jpg" in ct or "image/png" in ct:
                    return True
            elif resp.status_code == 405:
                range_resp = await client.get(clean, headers={"Range": "bytes=0-512"})
                if range_resp.status_code in (200, 206):
                    ct = range_resp.headers.get("content-type", "").lower()
                    if "image/jpeg" in ct or "image/jpg" in ct or "image/png" in ct:
                        return True
    except Exception as e:
        logger.debug(f"Image accessibility check failed for {clean}: {e}")
    return False


def build_event_inline_result(
    event: Any,
    deep_link: Optional[str] = None,
    is_share: bool = False
) -> Dict[str, Any]:
    """
    Builds a compliant InlineQueryResult (Photo with fallback to Article)
    shared across Share V2 (savePreparedInlineMessage) and Inline Search (answerInlineQuery).
    When photo is present, produces InlineQueryResultPhoto so Telegram sends the full media card with button into the chat.
    """
    raw_id = getattr(event, "id", "0")
    clean_id = str(raw_id).replace("event_", "").strip()
    result_id = f"share_{clean_id}" if is_share else f"event_{clean_id}"

    if not deep_link:
        deep_link = settings.get_event_deep_link(clean_id)

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "Открыть событие 🧭", "url": deep_link}
            ]
        ]
    }

    caption = format_event_card_caption(event)
    raw_title = getattr(event, "title", "Мероприятие")
    title_str = str(raw_title).strip() if isinstance(raw_title, str) else "Мероприятие"

    venue_display = format_event_venue_str(event)
    date_str = format_event_date_str(event)
    price_line = format_event_price_line(event) or ""
    desc_parts = [
        str(p).strip()
        for p in [venue_display, date_str, price_line]
        if p and isinstance(p, str) and str(p).strip()
    ]
    description = " · ".join(desc_parts)

    raw_cover = getattr(event, "cover_image_url", None)
    has_cover = bool(raw_cover and isinstance(raw_cover, str) and raw_cover.strip())

    if has_cover:
        photo_url = optimize_preview_image_url(raw_cover, is_thumbnail=False)
        thumb_url = optimize_preview_image_url(raw_cover, is_thumbnail=True)
        return {
            "type": "photo",
            "id": result_id,
            "photo_url": photo_url,
            "thumbnail_url": thumb_url,
            "title": f"🎟 {title_str}",
            "description": description,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }
    else:
        fallback_thumb = resolve_absolute_image_url(None)
        return {
            "type": "article",
            "id": result_id,
            "title": f"🎟 {title_str}",
            "description": description,
            "thumbnail_url": fallback_thumb,
            "thumb_url": fallback_thumb,
            "input_message_content": {
                "message_text": caption,
                "parse_mode": "HTML"
            },
            "reply_markup": reply_markup
        }


async def save_prepared_inline_share_message(
    user_telegram_id: int,
    event: Any,
    deep_link: str
) -> Dict[str, Any]:
    """
    Creates a prepared inline message via Telegram Bot API savePreparedInlineMessage.
    Binds the message strictly to the authenticated user_telegram_id.
    Uses unified build_event_inline_result with is_share=True.
    Returns: {"prepared_message_id": id, "expiration_date": timestamp}
    """
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN.startswith("123456789:"):
        clean_id = str(getattr(event, "id", "0")).replace("event_", "").strip()
        return {
            "prepared_message_id": f"mock_prep_{clean_id}",
            "expiration_date": 1799999999
        }

    inline_result = build_event_inline_result(event=event, deep_link=deep_link, is_share=True)

    payload = {
        "user_id": int(user_telegram_id),
        "result": inline_result,
        "allow_user_chats": True,
        "allow_bot_chats": False,
        "allow_group_chats": True,
        "allow_channel_chats": False
    }

    url = f"https://api.telegram.org/bot{settings.clean_bot_token}/savePreparedInlineMessage"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if not data.get("ok"):
                err_desc = data.get("description", "Unknown error from Telegram API")
                logger.warning(f"savePreparedInlineMessage Telegram API error: {err_desc}")
                raise RuntimeError(f"Telegram API error: {err_desc}")

            result_obj = data.get("result", {})
            return {
                "prepared_message_id": result_obj.get("id"),
                "expiration_date": result_obj.get("expiration_date")
            }
    except Exception as e:
        logger.error(f"Failed to save prepared inline message for user {user_telegram_id}: {e}")
        raise


async def handle_inline_query(
    session: AsyncSession,
    inline_query: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Processes Telegram InlineQuery (@evently ...) and constructs response payload for answerInlineQuery.
    Supports dynamic city recognition across 1,134 cities and keyword fallback.
    """
    query_id = inline_query.get("id", "")
    query_text = (inline_query.get("query") or "").strip()
    user = inline_query.get("from", {})
    user_id = user.get("id")

    # Fast-path: Direct event lookup by ID (e.g. from Mini App 'Позвать друга' switchInlineQuery)
    target_event_id: Optional[str] = None
    cleaned_lower = query_text.strip().lower()
    if cleaned_lower.startswith("event_"):
        target_event_id = query_text.strip()[6:].strip()
    elif cleaned_lower.startswith("event "):
        target_event_id = query_text.strip()[6:].strip()

    if target_event_id:
        try:
            from app.services.event_service import get_event_details
            event_details = await get_event_details(session, target_event_id)
            if event_details:
                return {
                    "inline_query_id": query_id,
                    "results": [
                        build_event_inline_result(event_details, is_share=False)
                    ],
                    "cache_time": 10,
                    "is_personal": True
                }
        except Exception as e:
            logger.warning(f"Error fetching specific event for inline query '{target_event_id}': {e}")

    # 1. Parse structured city/category/date
    parsed = parse_query(query_text, default_city_id=None)
    target_city_id = parsed.city_id
    search_keyword = None

    # If city not extracted by pattern parser, check if query matches a city name in DB
    if not target_city_id and query_text:
        cleaned = query_text.strip().lower()
        city_res = await session.execute(
            select(City).where(or_(City.name.ilike(f"{cleaned}%"), City.id == cleaned)).limit(1)
        )
        matched_city = city_res.scalar_one_or_none()
        if matched_city:
            target_city_id = matched_city.id
        else:
            search_keyword = query_text
    elif not target_city_id:
        target_city_id = "makhachkala"

    # Fetch events
    events, total = await list_published_events(
        session=session,
        city_id=target_city_id,
        category_id=parsed.category_id,
        date_filter=parsed.date_filter,
        search_query=search_keyword,
        limit=10
    )

    # If no events found in targeted city but a generic keyword was typed, search across all cities
    if not events and not parsed.city_id and search_keyword:
        events, total = await list_published_events(
            session=session,
            city_id=None,
            category_id=parsed.category_id,
            date_filter=parsed.date_filter,
            search_query=search_keyword,
            limit=10
        )

    results: List[Dict[str, Any]] = []

    if events:
        for ev in events:
            results.append(build_event_inline_result(ev, is_share=False))

    # Also search matching organizations if query is present
    if query_text:
        try:
            from app.services.discovery_service import discovery_service
            matched_orgs, _ = await discovery_service.search_organizations(
                session=session,
                query=query_text,
                city_id=target_city_id if target_city_id != "makhachkala" or "махачкал" in query_text.lower() else None,
                limit=3
            )
            for org in matched_orgs:
                org_thumb = resolve_absolute_image_url(org.avatar_url)
                org_url = settings.get_organization_deep_link(org.id)
                results.append({
                    "type": "article",
                    "id": f"org_{org.id}",
                    "title": f"🧭 {org.name}",
                    "description": f"{org.category} · {org.city_name or ''} · {org.followers_count} подписчиков",
                    "thumbnail_url": org_thumb,
                    "thumb_url": org_thumb,
                    "input_message_content": {
                        "message_text": (
                            f"🧭 <b>{html.escape(org.name)}</b>\n"
                            f"Категория: {html.escape(org.category)}\n"
                            f"Город: {html.escape(org.city_name or 'Россия')}\n"
                            f"Подписчиков: {org.followers_count}\n\n"
                            f"Смотрите актуальные события и афишу организации в Ivently!"
                        ),
                        "parse_mode": "HTML"
                    },
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": "🧭 Открыть профиль", "url": org_url}]
                        ]
                    }
                })
        except Exception as e:
            logger.warning(f"Error querying organizations for inline search: {e}")

    if not results:
        # Graceful empty-state
        city_display = (target_city_id or "выбранном городе").capitalize()
        empty_thumb = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=400"
        display_q = html.escape(query_text or "поиск")
        results.append({
            "type": "article",
            "id": "empty_state",
            "title": f"В {city_display} пока нет подходящих событий",
            "description": "Нажмите, чтобы открыть всю афишу Ivently в Mini App",
            "thumbnail_url": empty_thumb,
            "thumb_url": empty_thumb,
            "input_message_content": {
                "message_text": (
                    f"🔍 <b>По запросу «{display_q}» событий не найдено.</b>\n\n"
                    f"Откройте Ivently Mini App, чтобы посмотреть события в других городах или категориях."
                ),
                "parse_mode": "HTML"
            },
            "reply_markup": build_catalog_inline_keyboard()
        })

    return {
        "inline_query_id": query_id,
        "results": results,
        "cache_time": 30,
        "cache_time": 30,
        "is_personal": True
    }


def handle_private_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Handles private bot commands (/start, /create, /admin, /help) and text messages.
    Returns outbound sendMessage payload.
    """
    text = (message.get("text") or "").strip()
    chat_id = message.get("chat", {}).get("id")
    user = message.get("from", {})
    user_id = user.get("id")

    if not text or not chat_id:
        return None

    bot_username = settings.clean_bot_username

    if text.startswith("/start"):
        start_param = text.split(" ")[1] if len(text.split(" ")) > 1 else ""
        return {
            "chat_id": chat_id,
            "text": (
                "👋 <b>Добро пожаловать в Ivently — события рядом!</b>\n\n"
                "Находите концерты, вечеринки, спорт, митапы и другие события в вашем городе.\n\n"
                "🔎 <b>Найти события</b> — поиск прямо из любого чата.\n"
                "📍 Выберите город или разрешите определить его автоматически.\n"
                "✨ Откройте Ivently, чтобы смотреть афишу и отмечать «Я иду»."
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("🧭 Открыть Ivently", start_param or None, style="primary")
                    ],
                    [
                        {"text": "🔎 Найти события", "switch_inline_query": ""}
                    ],
                    [
                        build_mini_app_button("➕ Создать мероприятие", "create")
                    ]
                ]
            }
        }

    elif text.startswith("/create"):
        return {
            "chat_id": chat_id,
            "text": (
                "📢 <b>Создание нового мероприятия</b>\n\n"
                "Организуете концерт, вечеринку, лекцию или турнир? "
                "Заполните простую форму в Mini App. После быстрой модерации ваше событие появится в общей афише!"
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("➕ Заполнить форму события", "create")
                    ]
                ]
            }
        }

    elif text.startswith("/admin"):
        if settings.is_admin(user_id):
            return {
                "chat_id": chat_id,
                "text": (
                    "🛡️ <b>Панель администратора Ivently</b>\n\n"
                    f"Ваш Telegram ID: <code>{user_id}</code>\n\n"
                    "Вы авторизованы как администратор. "
                    "Вам доступны функции модерации заявок, публикации и отмены мероприятий."
                ),
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            build_mini_app_button("🛡️ Открыть модерацию", "admin")
                        ]
                    ]
                }
            }
        else:
            return {
                "chat_id": chat_id,
                "text": (
                    f"⛔ <b>У вас нет прав администратора</b> для использования этой команды.\n\n"
                    f"Ваш Telegram ID: <code>{user_id}</code>\n\n"
                    f"Чтобы получить доступ к панели модерации, добавьте этот ID в переменную окружения <code>ADMIN_USER_IDS</code> в настройках проекта Ivently."
                ),
                "parse_mode": "HTML"
            }

    elif text.startswith("/events"):
        return {
            "chat_id": chat_id,
            "text": (
                "🧭 <b>Афиша мероприятий Ivently</b>\n\n"
                "Смотрите актуальные концерты, спектакли, лекции, вечеринки и спорт в вашем городе!\n\n"
                "Нажмите кнопку ниже, чтобы открыть афишу в Mini App:"
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("🧭 Открыть афишу", style="primary")
                    ],
                    [
                        {"text": "🔎 Поиск в чате", "switch_inline_query": ""}
                    ]
                ]
            }
        }

    elif text.startswith("/help"):
        return {
            "chat_id": chat_id,
            "text": (
                "ℹ️ <b>Как пользоваться Ivently:</b>\n\n"
                "1. <b>Быстрый поиск в любом чате:</b>\n"
                f"   Нажмите «🔎 Найти события» или напишите <code>@{bot_username} [город] [категория/дата]</code> прямо в строке ввода сообщения.\n\n"
                "2. <b>Telegram Mini App:</b>\n"
                "   Нажмите кнопку ниже, чтобы открыть афишу, фильтровать события и отмечаться «Я иду».\n\n"
                "3. <b>Команды бота:</b>\n"
                "   /events — открыть афишу\n"
                "   /create — создать мероприятие или профиль организации\n"
                "   /help — справка"
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("🧭 Открыть Ivently", style="primary")
                    ],
                    [
                        {"text": "🔎 Найти события", "switch_inline_query": ""}
                    ]
                ]
            }
        }

    else:
        # Fallback response for any other private text messages
        return {
            "chat_id": chat_id,
            "text": (
                "👋 Привет! Чтобы найти события или открыть афишу, нажмите кнопку ниже "
                f"или вызовите бота в любом чате: <code>@{bot_username} концерты</code>"
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("🧭 Открыть Ivently", style="primary")
                    ]
                ]
            }
        }

