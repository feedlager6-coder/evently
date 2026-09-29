from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["Meta"])


@router.get("/meta")
async def get_app_meta():
    """Returns general public application metadata and bot configuration."""
    return {
        "app_name": settings.APP_NAME,
        "bot_username": settings.clean_bot_username,
        "mini_app_url": settings.effective_mini_app_url,
    }
