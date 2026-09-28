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


def build_event_inline_keyboard(event_id: str) -> Dict[str, Any]:
    """
    Constructs compliant inline keyboard to open event directly inside Telegram Mini App.
    Uses Telegram's universal direct link pattern: https://t.me/<bot>/<app>?startapp=<param>
    """
    url = f"{settings.TELEGRAM_MINI_APP_URL}?startapp=event_{event_id}"
    return {
        "inline_keyboard": [
            [
                {"text": "🎟️ Открыть афишу в Mini App", "url": url}
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
            results.append({
                "type": "article",
                "id": f"event_{ev.id}",
                "title": ev.title,
                "description": f"{ev.city_name} · {date_str} · {price_str}",
                "thumb_url": ev.cover_image_url or "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?w=400",
                "input_message_content": {
                    "message_text": format_event_message(ev),
                    "parse_mode": "HTML"
                },
                "reply_markup": build_event_inline_keyboard(ev.id)
            })
    else:
        # Graceful empty-state
        city_display = parsed.city_id.capitalize() if parsed.city_id else "выбранном городе"
        results.append({
            "type": "article",
            "id": "empty_state",
            "title": f"В {city_display} пока нет подходящих событий",
            "description": "Нажмите, чтобы открыть всю афишу Evently в Mini App",
            "thumb_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=400",
            "input_message_content": {
                "message_text": (
                    f"🔍 <b>По запросу «{query_text}» событий не найдено.</b>\n\n"
                    f"Откройте Evently Mini App, чтобы посмотреть события в других городах или категориях."
                ),
                "parse_mode": "HTML"
            },
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "🎟️ Открыть Evently Mini App", "url": settings.TELEGRAM_MINI_APP_URL}
                    ]
                ]
            }
        })

    return {
        "inline_query_id": query_id,
        "results": results,
        "cache_time": 30,
        "is_personal": True
    }


def handle_private_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Handles private bot commands (/start, /create, /admin).
    Returns outbound sendMessage payload if command matched.
    """
    text = (message.get("text") or "").strip()
    chat_id = message.get("chat", {}).get("id")
    user = message.get("from", {})
    user_id = user.get("id")

    if not text or not chat_id:
        return None

    if text.startswith("/start"):
        start_param = text.split(" ")[1] if len(text.split(" ")) > 1 else ""
        app_url = f"{settings.TELEGRAM_MINI_APP_URL}?startapp={start_param}" if start_param else settings.TELEGRAM_MINI_APP_URL
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
                        {"text": "🎟️ Открыть Evently", "url": app_url}
                    ],
                    [
                        {"text": "➕ Создать мероприятие", "url": f"{settings.TELEGRAM_MINI_APP_URL}?startapp=create"}
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
                        {"text": "➕ Заполнить форму события", "url": f"{settings.TELEGRAM_MINI_APP_URL}?startapp=create"}
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
                            {"text": "🛡️ Открыть модерацию", "url": f"{settings.TELEGRAM_MINI_APP_URL}?startapp=admin"}
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

    return None
