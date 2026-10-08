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
    fallback = "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=400"
    if not url or not url.strip():
        return fallback
    clean = url.strip()
    if clean.startswith("http://") or clean.startswith("https://"):
        return clean
    public_host = settings.effective_public_host
    if public_host and clean.startswith("/"):
        return f"{public_host}{clean}"
    return fallback


def format_event_message(event: EventSummary) -> str:
    """Formats event preview text for Telegram messages with HTML styling."""
    price_text = "Бесплатно" if event.is_free else f"{event.price_amount} {event.price_currency}"
    date_str = event.start_at.strftime("%d.%m.%Y в %H:%M")
    safe_title = html.escape(event.title)
    safe_venue = html.escape(event.venue_name)
    safe_city = html.escape(event.city_name or event.city_id or "")

    return (
        f"🧭 <b>{safe_title}</b>\n"
        f"📅 {date_str}\n"
        f"📍 {safe_venue} ({safe_city})\n"
        f"💰 {price_text}\n"
        f"👥 {event.attendee_count} человек(а) идут"
    )


def build_mini_app_button(
    text: str,
    start_param: Optional[str] = None,
    style: Optional[str] = None
) -> Dict[str, Any]:
    """
    Builds compliant button for private bot messages.
    Supports official Telegram Bot API 'style' parameter ('primary', 'success', 'danger').
    Priority 1: If effective_public_host is available (e.g. Railway HTTPS), use 'web_app' button.
    This launches the native Telegram Mini App webview directly with initData,
    without requiring a custom BotFather short name.
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
    Constructs compliant inline keyboard to open event directly inside Telegram Mini App.
    In inline query results (sent in group chats/channels), only direct 'url' buttons are allowed.
    """
    url = settings.get_event_deep_link(event_id)
    return {
        "inline_keyboard": [
            [
                {"text": "🧭 Открыть в Mini App", "url": url}
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


async def save_prepared_inline_share_message(
    user_telegram_id: int,
    event: Any,
    deep_link: str
) -> Dict[str, Any]:
    """
    Creates a prepared inline message via Telegram Bot API savePreparedInlineMessage.
    Binds the message strictly to the authenticated user_telegram_id.
    Uses InlineQueryResultPhoto if public image is valid, otherwise falls back to InlineQueryResultArticle.
    Returns: {"prepared_message_id": id, "expiration_date": timestamp}
    """
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN.startswith("123456789:"):
        return {
            "prepared_message_id": f"mock_prep_{getattr(event, 'id', '0')}",
            "expiration_date": 1799999999
        }

    price_str = "Бесплатно" if getattr(event, "is_free", False) else f"{getattr(event, 'price_amount', 0)} {getattr(event, 'price_currency', None) or 'RUB'}"
    start_at = getattr(event, "start_at", None)
    date_str = start_at.strftime("%d.%m.%Y в %H:%M") if start_at else "Дата уточняется"
    venue_str = getattr(event, "venue_name", None) or "Локация в приложении"
    city_name = getattr(event, "city_name", None) or ""
    venue_display = f"{venue_str}, {city_name}" if city_name else venue_str

    caption_text = (
        f"🎟 <b>{html.escape(getattr(event, 'title', ''))}</b>\n\n"
        f"🗓 {date_str}\n"
        f"📍 {html.escape(venue_display)}\n"
        f"💰 {price_str}"
    )

    inline_keyboard = {
        "inline_keyboard": [
            [
                {"text": "Открыть событие 🧭", "url": deep_link}
            ]
        ]
    }

    cover_url = getattr(event, "cover_image_url", None)
    resolved_cover = resolve_absolute_image_url(cover_url) if cover_url else None
    has_valid_photo = await check_public_image_validity(resolved_cover)

    result_id = f"share_{getattr(event, 'id', '0')}"
    if has_valid_photo and resolved_cover:
        inline_result: Dict[str, Any] = {
            "type": "photo",
            "id": result_id,
            "photo_url": resolved_cover,
            "thumbnail_url": resolved_cover,
            "caption": caption_text,
            "parse_mode": "HTML",
            "reply_markup": inline_keyboard
        }
    else:
        inline_result = {
            "type": "article",
            "id": result_id,
            "title": f"🎟 {getattr(event, 'title', '')}",
            "description": f"{city_name} · {date_str} · {price_str}",
            "thumbnail_url": resolve_absolute_image_url(None),
            "thumb_url": resolve_absolute_image_url(None),
            "input_message_content": {
                "message_text": caption_text,
                "parse_mode": "HTML"
            },
            "reply_markup": inline_keyboard
        }

    payload = {
        "user_id": int(user_telegram_id),
        "result": inline_result,
        "allow_user_chats": True,
        "allow_bot_chats": False,
        "allow_group_chats": True,
        "allow_channel_chats": False
    }

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/savePreparedInlineMessage"
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
                price_str = "Бесплатно" if event_details.is_free else f"{event_details.price_amount} {event_details.price_currency or 'RUB'}"
                date_str = event_details.start_at.strftime("%d.%m.%Y в %H:%M")
                thumb = resolve_absolute_image_url(event_details.cover_image_url)
                venue_label = event_details.venue_name or (event_details.city_name or "Локация в приложении")
                deep_link = settings.get_event_deep_link(event_details.id)
                msg_text = (
                    f"Пойдём вместе на «<b>{html.escape(event_details.title)}</b>»!\n\n"
                    f"🗓 {date_str}\n"
                    f"📍 {html.escape(venue_label)} ({html.escape(event_details.city_name or '')})\n"
                    f"💰 {price_str}\n\n"
                    f"Посмотреть событие в Ivently:\n"
                    f"{deep_link}"
                )
                return {
                    "inline_query_id": query_id,
                    "results": [
                        {
                            "type": "article",
                            "id": f"event_{event_details.id}",
                            "title": f"🎟 {event_details.title}",
                            "description": f"{event_details.city_name or ''} · {date_str} · {price_str}",
                            "thumbnail_url": thumb,
                            "thumb_url": thumb,
                            "input_message_content": {
                                "message_text": msg_text,
                                "parse_mode": "HTML"
                            },
                            "reply_markup": {
                                "inline_keyboard": [
                                    [
                                        {"text": "🧭 Открыть в Mini App", "url": deep_link}
                                    ]
                                ]
                            }
                        }
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
            price_str = "Бесплатно" if ev.is_free else f"{ev.price_amount} {ev.price_currency}"
            date_str = ev.start_at.strftime("%d.%m %H:%M")
            thumb = resolve_absolute_image_url(ev.cover_image_url)
            results.append({
                "type": "article",
                "id": f"event_{ev.id}",
                "title": ev.title,
                "description": f"{ev.city_name} · {date_str} · {price_str}",
                "thumbnail_url": thumb,
                "thumb_url": thumb,
                "input_message_content": {
                    "message_text": format_event_message(ev),
                    "parse_mode": "HTML"
                },
                "reply_markup": build_event_inline_keyboard(ev.id)
            })

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

