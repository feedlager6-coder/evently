import logging
import httpx
from typing import Dict, Any
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.services.telegram_bot import handle_inline_query, handle_private_message

logger = logging.getLogger("evently.telegram_webhook")

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])


@router.post("/webhook")
async def telegram_webhook(
    update: Dict[str, Any],
    session: AsyncSession = Depends(get_db)
):
    """
    Ingests and routes Telegram updates:
    - inline_query (@evently ...) -> handle_inline_query
    - message (/start, /create, /admin) -> handle_private_message
    """
    update_id = update.get("update_id")
    response_payload = None

    is_live_bot = bool(
        settings.TELEGRAM_BOT_TOKEN
        and "testtoken" not in settings.TELEGRAM_BOT_TOKEN
        and not settings.TELEGRAM_BOT_TOKEN.startswith("123456789:")
        and ":" in settings.TELEGRAM_BOT_TOKEN
    )

    if "inline_query" in update:
        inline_query = update["inline_query"]
        answer_payload = await handle_inline_query(session, inline_query)
        response_payload = {
            "method": "answerInlineQuery",
            **answer_payload
        }

        # Dispatch upstream to Telegram if live bot token is configured
        if is_live_bot:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerInlineQuery",
                        json=answer_payload
                    )
                    if resp.status_code != 200 or not resp.json().get("ok"):
                        logger.error(f"Telegram answerInlineQuery error ({resp.status_code}): {resp.text}")
                    else:
                        logger.info(f"Answered inline query {answer_payload.get('inline_query_id')}")
            except Exception as e:
                logger.error(f"Failed to post answerInlineQuery to Telegram: {e}")

        return {"ok": True, "type": "inline_query", "payload": response_payload}

    elif "message" in update:
        msg = update["message"]
        reply_payload = handle_private_message(msg)
        if reply_payload:
            response_payload = {
                "method": "sendMessage",
                **reply_payload
            }

            if is_live_bot:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.post(
                            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                            json=reply_payload
                        )
                        if resp.status_code != 200 or not resp.json().get("ok"):
                            logger.error(f"Telegram sendMessage error ({resp.status_code}): {resp.text}")
                        else:
                            logger.info(f"Sent reply to chat {reply_payload.get('chat_id')}")
                except Exception as e:
                    logger.error(f"Failed to post sendMessage to Telegram: {e}")

            return {"ok": True, "type": "message", "payload": response_payload}

    return {"ok": True, "type": "ignored", "update_id": update_id}
