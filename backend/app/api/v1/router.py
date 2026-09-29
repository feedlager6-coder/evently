from fastapi import APIRouter

from app.api.v1.cities import router as cities_router
from app.api.v1.categories import router as categories_router
from app.api.v1.events import router as events_router
from app.api.v1.organizer import router as organizer_router
from app.api.v1.admin import router as admin_router
from app.api.v1.telegram import router as telegram_router
from app.api.v1.locations import router as locations_router
from app.api.v1.users import router as users_router
from app.api.v1.meta import router as meta_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(cities_router)
api_v1_router.include_router(categories_router)
api_v1_router.include_router(events_router)
api_v1_router.include_router(organizer_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(telegram_router)
api_v1_router.include_router(locations_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(meta_router)

__all__ = ["api_v1_router"]


