"""
Evently — Telegram Local Verification & Management CLI

Usage:
    # 1. Inspect Bot status and settings (reads .env):
    python backend/scripts/telegram_cli.py info

    # 2. Register Webhook with a public tunnel (Cloudflare Tunnel, ngrok, localtunnel):
    python backend/scripts/telegram_cli.py webhook --set https://your-tunnel-url.trycloudflare.com

    # 3. Check current Webhook status:
    python backend/scripts/telegram_cli.py webhook --info

    # 4. Remove Webhook:
    python backend/scripts/telegram_cli.py webhook --delete

    # 5. Run local long-polling (alternative to webhook for bot events):
    python backend/scripts/telegram_cli.py poll
"""

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
import argparse
from typing import Optional
import httpx

from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.telegram_bot import handle_inline_query, handle_private_message


def check_token():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or "testtoken" in token or token.startswith("123456789:"):
        print("❌ Error: TELEGRAM_BOT_TOKEN is not configured or still set to demo placeholder in .env")
        print("   Please provide a real Telegram bot token from @BotFather in .env to use live verification.")
        sys.exit(1)
    return token


async def get_bot_info():
    token = check_token()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        data = resp.json()
        if not data.get("ok"):
            print(f"❌ Failed to reach Telegram API: {data.get('description')}")
            return

        user = data["result"]
        print("\n🤖 Telegram Bot Information:")
        print(f"   • Bot ID:       {user.get('id')}")
        print(f"   • First Name:   {user.get('first_name')}")
        print(f"   • Username:     @{user.get('username')}")
        print(f"   • Can Read All: {user.get('can_read_all_group_messages', False)}")
        print(f"   • Inline Mode:  {user.get('supports_inline_queries', False)}")

        if not user.get("supports_inline_queries"):
            print("\n⚠️ WARNING: Inline mode is NOT enabled for this bot!")
            print("   To enable @evently inline queries:")
            print("   1. Open @BotFather in Telegram.")
            print("   2. Send /setinline, choose your bot, and enter placeholder text (e.g. 'Поиск событий...').")
        else:
            print("   ✅ Inline Mode is ENABLED in BotFather.")

        # Check webhook info
        wh_resp = await client.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
        wh_data = wh_resp.json().get("result", {})
        print("\n🌐 Current Webhook Status:")
        print(f"   • Webhook URL:            {wh_data.get('url') or '(None - polling mode)'}")
        print(f"   • Has Custom Certificate: {wh_data.get('has_custom_certificate', False)}")
        print(f"   • Pending Update Count:   {wh_data.get('pending_update_count', 0)}")
        if wh_data.get("last_error_message"):
            print(f"   • Last Webhook Error:     {wh_data.get('last_error_message')}")
            print(f"   • Last Error Date:        {wh_data.get('last_error_date')}")


async def set_webhook(tunnel_url: Optional[str] = None):
    token = check_token()
    target_url = tunnel_url or (f"https://{settings.PUBLIC_HOST}" if settings.PUBLIC_HOST else None)
    if not target_url:
        print("❌ Error: No URL provided and PUBLIC_HOST is not set in environment.")
        print("   Usage: python backend/scripts/telegram_cli.py webhook --set https://your-domain.com")
        return

    clean_url = target_url.rstrip("/")
    if not clean_url.startswith("https://"):
        print("❌ Error: Telegram Webhooks strictly require an HTTPS URL.")
        return

    full_webhook_url = f"{clean_url}/api/v1/telegram/webhook"
    print(f"📡 Setting Telegram webhook to: {full_webhook_url} ...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": full_webhook_url, "allowed_updates": ["inline_query", "message"]}
        )
        data = resp.json()
        if data.get("ok"):
            print("✅ Webhook registered successfully with Telegram!")
        else:
            print(f"❌ Failed to set webhook: {data.get('description')}")


async def delete_webhook():
    token = check_token()
    print("🗑️ Removing Telegram webhook...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
        data = resp.json()
        if data.get("ok"):
            print("✅ Webhook successfully removed (bot can now use polling).")
        else:
            print(f"❌ Failed to delete webhook: {data.get('description')}")


async def run_polling():
    token = check_token()
    print(f"🚀 Starting Evently Telegram Polling loop for bot @{settings.TELEGRAM_BOT_USERNAME}...")
    print("   Press Ctrl+C to stop.\n")

    # Clear webhook first
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")

    offset = 0
    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            try:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    json={"offset": offset, "timeout": 30, "allowed_updates": ["inline_query", "message"]}
                )
                if resp.status_code != 200:
                    await asyncio.sleep(2)
                    continue

                data = resp.json()
                updates = data.get("result", [])

                for upd in updates:
                    offset = upd["update_id"] + 1

                    if "inline_query" in upd:
                        iq = upd["inline_query"]
                        q_text = iq.get("query", "")
                        from_user = iq.get("from", {}).get("username") or iq.get("from", {}).get("first_name")
                        print(f"🔍 [InlineQuery] from @{from_user}: «{q_text}»")

                        async with AsyncSessionLocal() as session:
                            answer = await handle_inline_query(session, iq)

                        post_resp = await client.post(
                            f"https://api.telegram.org/bot{token}/answerInlineQuery",
                            json=answer
                        )
                        if post_resp.status_code == 200 and post_resp.json().get("ok"):
                            print(f"   ↳ Sent {len(answer.get('results', []))} results")
                        else:
                            print(f"   ↳ ❌ Error: {post_resp.text}")

                    elif "message" in upd:
                        msg = upd["message"]
                        text = msg.get("text", "")
                        from_user = msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name")
                        print(f"💬 [Message] from @{from_user}: «{text}»")

                        reply = handle_private_message(msg)
                        if reply:
                            post_resp = await client.post(
                                f"https://api.telegram.org/bot{token}/sendMessage",
                                json=reply
                            )
                            if post_resp.status_code == 200 and post_resp.json().get("ok"):
                                print(f"   ↳ Sent reply to chat {reply.get('chat_id')}")
                            else:
                                print(f"   ↳ ❌ Error: {post_resp.text}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ Polling loop error: {e}")
                await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Evently Telegram Verification CLI")
    subparsers = parser.add_subparsers(dest="command")

    # info
    subparsers.add_parser("info", help="Inspect bot status and settings")

    # webhook
    wh_parser = subparsers.add_parser("webhook", help="Manage Telegram webhook")
    wh_parser.add_argument("--set", type=str, nargs="?", const="", help="Public HTTPS URL (e.g. https://xxx.trycloudflare.com, defaults to PUBLIC_HOST)")
    wh_parser.add_argument("--info", action="store_true", help="Print current webhook status")
    wh_parser.add_argument("--delete", action="store_true", help="Delete webhook")

    # poll
    subparsers.add_parser("poll", help="Run local polling for bot events")

    args = parser.parse_args()

    if args.command == "info":
        asyncio.run(get_bot_info())
    elif args.command == "webhook":
        if args.set is not None:
            asyncio.run(set_webhook(args.set or None))
        elif args.delete:
            asyncio.run(delete_webhook())
        else:
            asyncio.run(get_bot_info())
    elif args.command == "poll":
        asyncio.run(run_polling())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
