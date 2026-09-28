import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    APP_NAME: str = "Evently"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./evently.db"

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_testtoken"
    TELEGRAM_BOT_USERNAME: str = "evently_bot"
    TELEGRAM_MINI_APP_URL: str = "https://t.me/evently_bot/app"

    # Admin Telegram IDs (comma-separated or list of ints)
    ADMIN_USER_IDS: str = "123456789,987654321"

    # Security & Networking
    SECRET_KEY: str = "evently_mvp_secret_key_change_in_production_32bytes"
    AUTH_DATE_MAX_AGE_SECONDS: int = 86400
    PUBLIC_HOST: Optional[str] = None
    CORS_ORIGINS: str = "*"

    # TypeSafe AI (Optional Secondary Layer)
    TYPESAFE_API_KEY: Optional[str] = None
    TYPESAFE_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator(
        "DATABASE_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BOT_USERNAME",
        "TELEGRAM_MINI_APP_URL",
        "ADMIN_USER_IDS",
        "SECRET_KEY",
        "PUBLIC_HOST",
        mode="before"
    )
    @classmethod
    def clean_strings(cls, v):
        if isinstance(v, str):
            v = v.strip().strip("'\"").strip()
        return v

    @property
    def clean_bot_token(self) -> str:
        """Returns sanitized Telegram bot token with whitespace/quotes stripped."""
        tok = (self.TELEGRAM_BOT_TOKEN or "").strip().strip("'\"").strip()
        return tok

    @property
    def is_live_bot(self) -> bool:
        """
        Determines whether TELEGRAM_BOT_TOKEN is a live, configured Telegram Bot API token.
        Telegram Bot tokens format: <bot_id_digits>:<token_secret>
        """
        tok = self.clean_bot_token
        if not tok or ":" not in tok:
            return False
        if "testtoken" in tok or tok == "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_testtoken":
            return False
        parts = tok.split(":", 1)
        return parts[0].isdigit() and len(parts[1]) >= 10

    @property
    def effective_public_host(self) -> Optional[str]:
        """
        Resolves public HTTPS host for Telegram Webhook and Mini App.
        Priority:
        1. settings.PUBLIC_HOST
        2. RAILWAY_PUBLIC_DOMAIN (automatically assigned by Railway)
        3. RAILWAY_STATIC_URL
        """
        host = (
            self.PUBLIC_HOST
            or os.getenv("RAILWAY_PUBLIC_DOMAIN")
            or os.getenv("RAILWAY_STATIC_URL")
        )
        if not host:
            return None
        host = host.strip().strip("'\"").strip()
        if not host.startswith("http://") and not host.startswith("https://"):
            host = f"https://{host}"
        return host.rstrip("/")

    @property
    def effective_mini_app_url(self) -> str:
        """
        Resolves the Mini App URL.
        If TELEGRAM_MINI_APP_URL was set to a custom URL, uses it.
        If TELEGRAM_BOT_USERNAME is set to a custom bot, points to https://t.me/<username>/app.
        Otherwise falls back to effective_public_host or default.
        """
        custom_url = (self.TELEGRAM_MINI_APP_URL or "").strip().strip("'\"").strip()
        if custom_url and custom_url != "https://t.me/evently_bot/app":
            return custom_url
        if self.TELEGRAM_BOT_USERNAME and self.TELEGRAM_BOT_USERNAME != "evently_bot":
            return f"https://t.me/{self.TELEGRAM_BOT_USERNAME}/app"
        if self.effective_public_host:
            return self.effective_public_host
        return self.TELEGRAM_MINI_APP_URL

    @property
    def async_database_url(self) -> str:
        """
        Normalizes DATABASE_URL for SQLAlchemy async engine.
        Converts 'postgres://' or 'postgresql://' to 'postgresql+asyncpg://'.
        Leaves 'sqlite+aiosqlite://' or other explicit dialects intact.
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def admin_ids(self) -> List[int]:
        """Returns parsed list of integer admin Telegram IDs."""
        ids: List[int] = []
        for part in self.ADMIN_USER_IDS.split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    def is_admin(self, telegram_id: int) -> bool:
        """Verifies if telegram_id has admin privileges."""
        return telegram_id in self.admin_ids


settings = Settings()
