import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure backend directory is in sys.path regardless of execution root
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

from app.config import settings
from app.database import init_db, close_db, AsyncSessionLocal
from app.seeds.seed_data import seed_database
from app.api.v1.router import api_v1_router

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logger = logging.getLogger("evently")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize tables and seed data
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode...")
    await init_db()

    # Seed demo data
    async with AsyncSessionLocal() as session:
        try:
            await seed_database(session)
        except Exception as e:
            logger.error(f"Error seeding database: {e}")

    telegram_polling_task: Optional[asyncio.Task] = None

    # Telegram Update Delivery Strategy:
    # On Selectel (and anywhere inbound webhooks suffer TCP timeouts/DPI drops),
    # long-polling provides guaranteed zero-latency (<150ms) update delivery.
    if settings.is_live_bot:
        if settings.TELEGRAM_MODE == "polling":
            logger.info("Switching Telegram bot to long-polling mode (guaranteed zero-latency)...")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    del_resp = await client.post(
                        f"https://api.telegram.org/bot{settings.clean_bot_token}/deleteWebhook",
                        json={"drop_pending_updates": False}
                    )
                    logger.info(f"Telegram webhook deleted for polling: {del_resp.json().get('description')}")
            except Exception as e:
                logger.error(f"Failed to delete Telegram webhook for polling: {e}")

            async def telegram_polling_loop():
                try:
                    await asyncio.sleep(2)
                except asyncio.CancelledError:
                    return

                token = settings.clean_bot_token
                logger.info("🚀 Telegram long-polling loop started (instant update delivery)")
                offset = 0

                async with httpx.AsyncClient(timeout=35.0) as client:
                    while True:
                        try:
                            resp = await client.get(
                                f"https://api.telegram.org/bot{token}/getUpdates",
                                params={
                                    "offset": offset,
                                    "limit": 20,
                                    "timeout": 20,
                                    "allowed_updates": ["message", "inline_query"]
                                }
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                updates = data.get("result", [])
                                for update in updates:
                                    up_id = update.get("update_id")
                                    if up_id is not None:
                                        offset = max(offset, up_id + 1)

                                    try:
                                        async with AsyncSessionLocal() as session:
                                            from app.api.v1.telegram import dispatch_telegram_update
                                            await dispatch_telegram_update(
                                                update=update,
                                                session=session,
                                                http_client=client,
                                                bot_token=token
                                            )
                                    except Exception as up_err:
                                        logger.error(f"Error dispatching Telegram update {up_id}: {up_err}", exc_info=True)
                            elif resp.status_code == 409:
                                text = resp.text
                                logger.warning(f"Telegram polling conflict (409): {text}")
                                if "terminated by other getUpdates request" in text:
                                    import random
                                    delay = random.uniform(5, 10)
                                    await asyncio.sleep(delay)
                                else:
                                    await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
                                    await asyncio.sleep(3)
                            else:
                                logger.warning(f"Telegram getUpdates returned {resp.status_code}: {resp.text}")
                                await asyncio.sleep(2)
                        except asyncio.CancelledError:
                            logger.info("Telegram long-polling loop cancelled during shutdown")
                            break
                        except Exception as e:
                            logger.warning(f"Telegram polling network warning: {e}")
                            await asyncio.sleep(1)

            telegram_polling_task = asyncio.create_task(telegram_polling_loop())

        elif settings.effective_public_host and settings.APP_ENV == "production":
            webhook_url = f"{settings.effective_public_host}/api/v1/telegram/webhook"
            secret = settings.effective_webhook_secret
            logger.info(f"Checking/syncing Telegram webhook to: {webhook_url}")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    wh_payload = {
                        "url": webhook_url,
                        "allowed_updates": ["inline_query", "message"]
                    }
                    if secret:
                        wh_payload["secret_token"] = secret

                    set_resp = await client.post(
                        f"https://api.telegram.org/bot{settings.clean_bot_token}/setWebhook",
                        json=wh_payload
                    )
                    data = set_resp.json()
                    if data.get("ok"):
                        logger.info(f"✅ Telegram webhook synchronized with secret_token: {webhook_url}")
                    else:
                        logger.warning(f"⚠️ Telegram setWebhook response: {data.get('description')}")
            except Exception as e:
                logger.error(f"Failed to auto-sync Telegram webhook on startup: {e}")

    # Start periodic reminder runner in background (initial run at +5s, then every 15 minutes)
    async def reminder_loop():
        # Short initial warm-up delay for DB connections and app initialization
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            return

        while True:
            try:
                async with AsyncSessionLocal() as session:
                    from app.services.reminder_service import process_due_reminders
                    await process_due_reminders(session)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic reminder runner: {e}")

            try:
                await asyncio.sleep(900)
            except asyncio.CancelledError:
                break

    reminder_task = asyncio.create_task(reminder_loop())

    # Periodic external events synchronizer (Culture.RU live municipal feeds)
    # Initial run at +30s warmup, then every 6 hours
    async def external_events_sync_loop():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

        logger.info("🚀 External events background sync loop started (runs every 6h)")
        while True:
            try:
                async with AsyncSessionLocal() as session:
                    from app.services.external_sync_service import ExternalSyncService
                    logger.info("Starting scheduled external events synchronization...")
                    result = await ExternalSyncService.sync_external_events(session)
                    logger.info(
                        "Scheduled external sync complete: %d total synced (%d created, %d updated)",
                        result.get("total_synced", 0),
                        result.get("created", 0),
                        result.get("updated", 0),
                    )
            except asyncio.CancelledError:
                logger.info("External events sync loop cancelled during shutdown")
                break
            except Exception as e:
                logger.error(f"Error in scheduled external events sync: {e}", exc_info=True)

            try:
                await asyncio.sleep(6 * 3600)
            except asyncio.CancelledError:
                break

    external_sync_task = asyncio.create_task(external_events_sync_loop())

    yield

    # Shutdown: Cancel background tasks and close connections
    if telegram_polling_task:
        telegram_polling_task.cancel()
        try:
            await telegram_polling_task
        except asyncio.CancelledError:
            pass

    reminder_task.cancel()
    try:
        await reminder_task
    except asyncio.CancelledError:
        pass

    external_sync_task.cancel()
    try:
        await external_sync_task
    except asyncio.CancelledError:
        pass

    logger.info("Shutting down Evently backend...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Evently — Telegram-first event discovery platform API",
    lifespan=lifespan
)

# CORS Middleware (supports Telegram WebApp origin & local dev)
raw_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
has_wildcard = not raw_origins or "*" in raw_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=raw_origins if not has_wildcard else ["*"],
    allow_credentials=not has_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cross-Origin headers for uploads (required for Telegram Bot API inline crawler)
@app.middleware("http")
async def add_uploads_cross_origin_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/uploads/"):
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response

# Include API v1 Router
app.include_router(api_v1_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "debug": settings.DEBUG,
        "storage": storage_service.get_storage_diagnostics()
    }


@app.get("/verification/yandex", response_class=PlainTextResponse, tags=["Verification"])
@app.get("/verification/yandex/", response_class=PlainTextResponse, include_in_schema=False)
async def verify_yandex():
    """
    Public ownership verification endpoint for Yandex Distribution.
    Returns plain text verification code if configured via YANDEX_VERIFICATION_CODE.
    Returns 404 neutral response when not configured.
    """
    code = settings.YANDEX_VERIFICATION_CODE
    if not code or not code.strip():
        return PlainTextResponse("Verification unavailable", status_code=404)
    return PlainTextResponse(code.strip(), media_type="text/plain")


# Mount Uploads directory (supports Railway Persistent Volume or local storage)
from app.services.storage_service import storage_service
UPLOADS_DIR = storage_service.get_local_storage_dir()
(UPLOADS_DIR / "covers").mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "avatars").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Serve Frontend SPA if built bundle exists
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(
            FRONTEND_DIST_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if (
            full_path.startswith("api/")
            or full_path.startswith("uploads/")
            or full_path == "health"
            or full_path.startswith("verification/")
            or full_path == "verification"
        ):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        try:
            resolved_base = FRONTEND_DIST_DIR.resolve()
            target = (FRONTEND_DIST_DIR / full_path).resolve()
            if target.is_relative_to(resolved_base) and target.is_file():
                return FileResponse(target)
        except (ValueError, OSError):
            pass
        return FileResponse(
            FRONTEND_DIST_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

