from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.services.auth_service import parse_and_validate_init_data, get_or_create_user, AuthenticationError


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Extracts and cryptographically validates Telegram initData if passed in Authorization header.
    Format: 'Authorization: tma <raw_init_data>' or 'Authorization: Bearer <raw_init_data>'
    """
    if not authorization:
        return None

    init_data_raw = authorization
    if authorization.startswith("tma "):
        init_data_raw = authorization[4:].strip()
    elif authorization.startswith("Bearer "):
        init_data_raw = authorization[7:].strip()

    try:
        parsed_data = parse_and_validate_init_data(init_data_raw)
        user = await get_or_create_user(session, parsed_data.user)
        return user
    except AuthenticationError:
        return None
    except Exception:
        return None


async def get_current_user(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_db)
) -> User:
    """
    Mandatory authentication dependency for protected endpoints.
    Requires valid Telegram initData signature.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header with Telegram initData"
        )

    init_data_raw = authorization
    if authorization.startswith("tma "):
        init_data_raw = authorization[4:].strip()
    elif authorization.startswith("Bearer "):
        init_data_raw = authorization[7:].strip()

    try:
        parsed_data = parse_and_validate_init_data(init_data_raw)
        user = await get_or_create_user(session, parsed_data.user)
        return user
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Telegram authentication failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}"
        )


async def require_admin(
    user: User = Depends(get_current_user)
) -> User:
    """
    Enforces RBAC: requester must be a verified Telegram user listed in ADMIN_USER_IDS.
    """
    if not settings.is_admin(user.telegram_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: administrator privileges required"
        )
    return user
