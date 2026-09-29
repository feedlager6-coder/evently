import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.parser_service import parse_query, ParsedQuery
from app.services.event_service import list_published_events
from app.schemas.event import EventSummary

logger = logging.getLogger("evently.telegram")


def format_event_message(event: EventSummary) -> str:
    """Formats event preview text for Telegram messages with HTML styling."""
    price_text = "Бесплатно" if event.is_free else f"{event.price_amount} {event.price_currency}"
    date_str = event.start_at.strftime("%d.%m.%Y в %H:%M")

    return (
        f"🎟️ <b>{event.title}</b>\n"
        f"📅 {date_str}\n"
        f"📍 {event.venue_name} ({event.city_name or event.city_id})\n"
        f"💰 {price_text}\n"
        f"👥 {event.attendee_count} человек(а) идут"
    )


def build_mini_app_button(text: str, start_param: Optional[str] = None) -> Dict[str, Any]:
    """
    Builds compliant button for private bot messages.
    If Mini App URL is a direct web URL (https://... and not t.me), uses 'web_app' button
    which launches the native Telegram Mini App viewport inside Telegram.
    If it is a t.me direct link, uses 'url' button.
    """
    base_url = settings.effective_mini_app_url
    if base_url.startswith("https://t.me/"):
        if start_param:
            sep = "&" if "?" in base_url else "?"
            return {"text": text, "url": f"{base_url}{sep}startapp={start_param}"}
        return {"text": text, "url": base_url}

    # Direct HTTPS Web URL (e.g. Railway public domain)
    if start_param:
        target_url = f"{base_url.rstrip('/')}/?startapp={start_param}"
    else:
        target_url = base_url
    return {"text": text, "web_app": {"url": target_url}}


def build_event_inline_keyboard(event_id: str) -> Dict[str, Any]:
    """
    Constructs compliant inline keyboard to open event directly inside Telegram Mini App.
    In inline query results (sent in group chats/channels), only direct 'url' buttons are allowed.
    """
    mini_app_url = settings.effective_mini_app_url
    if mini_app_url.startswith("https://t.me/"):
        sep = "&" if "?" in mini_app_url else "?"
        url = f"{mini_app_url}{sep}startapp=event_{event_id}"
    else:
        url = f"{mini_app_url.rstrip('/')}/?startapp=event_{event_id}"
    return {
        "inline_keyboard": [
            [
                {"text": "🎟️ Открыть афишу в Mini App", "url": url}
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
                {"text": "🎟️ Открыть Evently Mini App", "url": mini_app_url}
            ]
        ]
    }



async def handle_inline_query(
    session: AsyncSession,
    inline_query: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Processes Telegram InlineQuery (@evently ...) and constructs response payload for answerInlineQuery.
    """
    query_id = inline_query.get("id", "")
    query_text = inline_query.get("query", "")
    user = inline_query.get("from", {})
    user_id = user.get("id")

    parsed = parse_query(query_text, default_city_id="warsaw")

    # Fetch events
    events, total = await list_published_events(
        session=session,
        city_id=parsed.city_id,
        category_id=parsed.category_id,
        date_filter=parsed.date_filter,
        limit=10
    )

    results: List[Dict[str, Any]] = []

    if events:
        for ev in events:
            price_str = "Бесплатно" if ev.is_free else f"{ev.price_amount} {ev.price_currency}"
            date_str = ev.start_at.strftime("%d.%m %H:%M")
            thumb = ev.cover_image_url or "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=400"
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
    else:
        # Graceful empty-state
        city_display = parsed.city_id.capitalize() if parsed.city_id else "выбранном городе"
        empty_thumb = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=400"
        results.append({
            "type": "article",
            "id": "empty_state",
            "title": f"В {city_display} пока нет подходящих событий",
            "description": "Нажмите, чтобы открыть всю афишу Evently в Mini App",
            "thumbnail_url": empty_thumb,
            "thumb_url": empty_thumb,
            "input_message_content": {
                "message_text": (
                    f"🔍 <b>По запросу «{query_text}» событий не найдено.</b>\n\n"
                    f"Откройте Evently Mini App, чтобы посмотреть события в других городах или категориях."
                ),
                "parse_mode": "HTML"
            },
            "reply_markup": build_catalog_inline_keyboard()
        })

    return {
        "inline_query_id": query_id,
        "results": results,
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

    if text.startswith("/start"):
        start_param = text.split(" ")[1] if len(text.split(" ")) > 1 else ""
        return {
            "chat_id": chat_id,
            "text": (
                "👋 <b>Добро пожаловать в Evently!</b>\n\n"
                "Evently — ваш Telegram-проводник в мир ярких событий, концертов, вечеринок и митапов.\n\n"
                "• Напишите в любом чате <code>@evently мероприятия в Варшаве</code> для быстрого поиска.\n"
                "• Или откройте Mini App ниже для полноценного каталога и отметки «Я иду»."
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("🎟️ Открыть Evently", start_param or None)
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
                    "🛡️ <b>Панель администратора Evently</b>\n\n"
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
                "text": "⛔ У вас нет прав администратора для использования этой команды.",
                "parse_mode": "HTML"
            }

    elif text.startswith("/help"):
        return {
            "chat_id": chat_id,
            "text": (
                "ℹ️ <b>Как пользоваться Evently:</b>\n\n"
                "1. <b>Быстрый поиск в любом чате:</b>\n"
                "   Напишите <code>@evently [город] [категория/дата]</code> прямо в строке ввода сообщения.\n\n"
                "2. <b>Telegram Mini App:</b>\n"
                "   Нажмите кнопку ниже, чтобы открыть афишу, фильтровать события и отмечаться «Я иду».\n\n"
                "3. <b>Организаторам:</b>\n"
                "   Используйте команду /create для добавления своего мероприятия."
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("🎟️ Открыть Evently")
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
                "или вызовите бота в любом чате: <code>@evently концерты</code>"
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        build_mini_app_button("🎟️ Открыть Evently")
                    ]
                ]
            }
        }
