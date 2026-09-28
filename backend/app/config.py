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
