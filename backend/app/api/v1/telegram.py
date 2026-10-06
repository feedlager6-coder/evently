import logging
import httpx
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.services.telegram_bot import handle_inline_query, handle_private_message, build_mini_app_button

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
    - message (/start, /create, /admin, /help) -> handle_private_message
    - write_access_allowed -> handles permission grant confirmation

    Ensures zero silent drop:
    If live bot token is present and online, dispatches directly via Telegram Bot API.
    If dispatch fails or in test/fallback mode, returns the Telegram method directly
    in the HTTP webhook response for Telegram Bot API to execute immediately.
    """
    update_id = update.get("update_id")
    logger.info(f"Received Telegram update: update_id={update_id}, keys={list(update.keys())}")

    try:
        if "inline_query" in update:
            inline_query = update["inline_query"]
            answer_payload = await handle_inline_query(session, inline_query)

            dispatched = False
            if settings.is_live_bot:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.post(
                            f"https://api.telegram.org/bot{settings.clean_bot_token}/answerInlineQuery",
                            json=answer_payload
                        )
                        if resp.status_code == 200 and resp.json().get("ok"):
                            dispatched = True
                            logger.info(f"Dispatched answerInlineQuery upstream for query {answer_payload.get('inline_query_id')}")
                        else:
                            logger.warning(f"Telegram answerInlineQuery upstream returned ({resp.status_code}): {resp.text}")
                except Exception as e:
                    logger.error(f"Failed to post answerInlineQuery upstream to Telegram: {e}")

            # If not dispatched upstream, return the method directly as webhook response
            if not dispatched:
                return {
                    "method": "answerInlineQuery",
                    **answer_payload
                }

            return {"ok": True, "type": "inline_query", "dispatched": True, "method": "answerInlineQuery"}

        elif "message" in update:
            msg = update["message"]
            if "write_access_allowed" in msg:
                chat_id = msg.get("chat", {}).get("id")
                user_id = msg.get("from", {}).get("id")
                logger.info(f"Telegram write_access_allowed received for user {user_id} in chat {chat_id}")
                reply_payload = {
                    "chat_id": chat_id,
                    "text": (
                        "🔔 <b>Уведомления включены!</b>\n\n"
                        "Теперь вы будете вовремя узнавать о событиях, изменениях в расписании "
                        "и новостях площадок, на которые подписаны."
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
            else:
                reply_payload = handle_private_message(msg)
            if reply_payload:
                dispatched = False
                if settings.is_live_bot:
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            resp = await client.post(
                                f"https://api.telegram.org/bot{settings.clean_bot_token}/sendMessage",
                                json=reply_payload
                            )
                            if resp.status_code == 200 and resp.json().get("ok"):
                                dispatched = True
                                logger.info(f"Dispatched sendMessage upstream for chat {reply_payload.get('chat_id')}")
                            else:
                                logger.warning(f"Telegram sendMessage upstream returned ({resp.status_code}): {resp.text}")
                    except Exception as e:
                        logger.error(f"Failed to post sendMessage upstream to Telegram: {e}")

                # If not dispatched upstream, return the method directly in webhook response
                # Telegram Bot API will execute this immediately!
                if not dispatched:
                    return {
                        "method": "sendMessage",
                        **reply_payload
                    }

                return {"ok": True, "type": "message", "dispatched": True, "method": "sendMessage"}

        return {"ok": True, "type": "ignored", "update_id": update_id}
    except Exception as e:
        logger.error(f"Error handling Telegram webhook update {update_id}: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "update_id": update_id}


@router.get("/info")
async def telegram_info():
    """
    Returns public diagnostics for Telegram integration without leaking secrets.
    """
    token_configured = settings.is_live_bot
    effective_host = settings.effective_public_host
    expected_webhook = f"{effective_host}/api/v1/telegram/webhook" if effective_host else None

    diag: Dict[str, Any] = {
        "bot_configured": token_configured,
        "bot_username": settings.TELEGRAM_BOT_USERNAME,
        "effective_public_host": effective_host,
        "expected_webhook_url": expected_webhook,
        "effective_mini_app_url": settings.effective_mini_app_url,
        "telegram_api_reachable": False,
        "bot_info": None,
        "webhook_info": None,
    }

    if token_configured:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                me_resp = await client.get(f"https://api.telegram.org/bot{settings.clean_bot_token}/getMe")
                if me_resp.status_code == 200 and me_resp.json().get("ok"):
                    diag["telegram_api_reachable"] = True
                    me = me_resp.json().get("result", {})
                    diag["bot_info"] = {
                        "id": me.get("id"),
                        "first_name": me.get("first_name"),
                        "username": me.get("username"),
                        "can_join_groups": me.get("can_join_groups"),
                        "supports_inline_queries": me.get("supports_inline_queries")
                    }

                wh_resp = await client.get(f"https://api.telegram.org/bot{settings.clean_bot_token}/getWebhookInfo")
                if wh_resp.status_code == 200 and wh_resp.json().get("ok"):
                    wh = wh_resp.json().get("result", {})
                    diag["webhook_info"] = {
                        "url": wh.get("url"),
                        "has_custom_certificate": wh.get("has_custom_certificate"),
                        "pending_update_count": wh.get("pending_update_count"),
                        "last_error_date": wh.get("last_error_date"),
                        "last_error_message": wh.get("last_error_message"),
                        "is_matched": bool(expected_webhook and wh.get("url") == expected_webhook)
                    }
        except Exception as e:
            diag["error"] = str(e)

    return diag


@router.post("/setup-webhook")
async def setup_webhook_endpoint(target_url: Optional[str] = None):
    """
    Registers or re-registers the webhook with Telegram Bot API.
    Uses target_url if provided, otherwise uses settings.effective_public_host.
    """
    if not settings.is_live_bot:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN is not configured with a valid live token."
        }

    host = target_url or settings.effective_public_host
    if not host:
        return {
            "ok": False,
            "error": "No target_url provided and neither PUBLIC_HOST nor RAILWAY_PUBLIC_DOMAIN is configured."
        }

    host = host.strip().strip("'\"").strip().rstrip("/")
    if not host.startswith("https://"):
        host = f"https://{host.lstrip('http://')}"

    webhook_url = f"{host}/api/v1/telegram/webhook"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.clean_bot_token}/setWebhook",
                json={
                    "url": webhook_url,
                    "allowed_updates": ["inline_query", "message"]
                }
            )
            data = resp.json()
            return {
                "ok": data.get("ok", False),
                "webhook_url": webhook_url,
                "description": data.get("description", ""),
                "telegram_result": data
            }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to connect to Telegram API: {str(e)}"
        }
