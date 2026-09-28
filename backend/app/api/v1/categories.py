from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.category import Category
from app.schemas.category import CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponse])
async def get_categories(
    session: AsyncSession = Depends(get_db)
):
    """Returns list of active event categories."""
    result = await session.execute(
        select(Category).where(Category.is_active == True)
    )
    return result.scalars().all()
