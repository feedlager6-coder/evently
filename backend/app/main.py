import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db, close_db, AsyncSessionLocal
from app.seeds.seed_data import seed_database
from app.api.v1.router import api_v1_router

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
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

    yield

    # Shutdown: Close connections
    logger.info("Shutting down Evently backend...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Evently — Telegram-first event discovery platform API",
    lifespan=lifespan
)

# CORS Middleware (supports Telegram WebApp origin & local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        "debug": settings.DEBUG
    }


# Serve Frontend SPA if built bundle exists
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "health":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = FRONTEND_DIST_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
