import json
import hmac
import hashlib
import time
from typing import Optional, Dict
from urllib.parse import parse_qsl, unquote
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.models.city import City
from app.schemas.telegram import TelegramUserPayload, TelegramInitDataParsed


class AuthenticationError(Exception):
    """Raised when Telegram initData verification fails."""
    pass


def parse_and_validate_init_data(init_data_raw: str, bot_token: Optional[str] = None) -> TelegramInitDataParsed:
    """
    Validates Telegram WebApp initData string using HMAC-SHA256 per official specification:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data_raw or not isinstance(init_data_raw, str):
        raise AuthenticationError("Missing initData string")

    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    parsed_items = dict(parse_qsl(init_data_raw, keep_blank_values=True))

    if "hash" not in parsed_items:
        raise AuthenticationError("Missing hash in initData")

    received_hash = parsed_items.pop("hash")

    # Construct data_check_string by sorting key=value pairs alphabetically joined with \n
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_items.items()))

    # secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()

    # expected_hash = HMAC_SHA256(secret_key, data_check_string).hexdigest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    # Constant-time comparison
    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthenticationError("Invalid initData cryptographic signature")

    # Validate auth_date freshness
    if "auth_date" not in parsed_items:
        raise AuthenticationError("Missing auth_date in initData")

    try:
        auth_date = int(parsed_items["auth_date"])
    except ValueError:
        raise AuthenticationError("Invalid auth_date format")

    now = int(time.time())
    if now - auth_date > settings.AUTH_DATE_MAX_AGE_SECONDS:
        raise AuthenticationError("initData signature has expired")

    # Extract user payload
    if "user" not in parsed_items:
        raise AuthenticationError("Missing user object in initData")

    try:
        user_json = json.loads(unquote(parsed_items["user"]))
        user_payload = TelegramUserPayload(**user_json)
    except Exception as e:
        raise AuthenticationError(f"Failed to parse user payload: {e}")

    return TelegramInitDataParsed(
        user=user_payload,
        auth_date=auth_date,
        hash=received_hash,
        query_id=parsed_items.get("query_id"),
        chat_type=parsed_items.get("chat_type"),
        chat_instance=parsed_items.get("chat_instance"),
        start_param=parsed_items.get("start_param"),
        raw_data=parsed_items
    )


async def get_or_create_user(session: AsyncSession, tg_user: TelegramUserPayload) -> User:
    """
    Retrieves or creates/updates a user based on cryptographically verified Telegram payload.
    """
    stmt = select(User).where(User.telegram_id == tg_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Sync latest name / username / avatar
        changed = False
        if user.username != tg_user.username:
            user.username = tg_user.username
            changed = True
        if user.first_name != tg_user.first_name:
            user.first_name = tg_user.first_name
            changed = True
        if user.last_name != tg_user.last_name:
            user.last_name = tg_user.last_name
            changed = True
        if tg_user.photo_url and user.avatar_url != tg_user.photo_url:
            user.avatar_url = tg_user.photo_url
            changed = True
        if changed:
            await session.commit()
            await session.refresh(user)
    else:
        # New users start without an arbitrary pre-assigned city.
        # City selection is explicitly confirmed by the user in the UI.
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            avatar_url=tg_user.photo_url,
            default_city_id=None
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user
