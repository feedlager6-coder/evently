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
from fastapi import FastAPI
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

    # Auto-sync Telegram webhook if live token and public host are configured
    if settings.is_live_bot and settings.effective_public_host:
        webhook_url = f"{settings.effective_public_host}/api/v1/telegram/webhook"
        logger.info(f"Checking/syncing Telegram webhook to: {webhook_url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                info_resp = await client.get(f"https://api.telegram.org/bot{settings.clean_bot_token}/getWebhookInfo")
                current_url = ""
                if info_resp.status_code == 200:
                    current_url = info_resp.json().get("result", {}).get("url", "")

                if current_url != webhook_url:
                    logger.info(f"Registering Telegram webhook: {webhook_url} (previous: '{current_url}')...")
                    set_resp = await client.post(
                        f"https://api.telegram.org/bot{settings.clean_bot_token}/setWebhook",
                        json={
                            "url": webhook_url,
                            "allowed_updates": ["inline_query", "message"]
                        }
                    )
                    data = set_resp.json()
                    if data.get("ok"):
                        logger.info(f"✅ Telegram webhook auto-registered: {webhook_url}")
                    else:
                        logger.warning(f"⚠️ Telegram setWebhook response: {data.get('description')}")
                else:
                    logger.info(f"✅ Telegram webhook already configured: {webhook_url}")
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

    yield

    # Shutdown: Cancel background tasks and close connections
    reminder_task.cancel()
    try:
        await reminder_task
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
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        file_path = FRONTEND_DIST_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            FRONTEND_DIST_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

