import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    APP_NAME: str = "Ivently"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./evently.db"

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_testtoken"
    TELEGRAM_BOT_USERNAME: str = "Ivently_bot"
    TELEGRAM_MINI_APP_URL: str = "https://t.me/Ivently_bot/app"
    TELEGRAM_MINI_APP_SHORT_NAME: Optional[str] = "app"

    # Admin Telegram IDs (comma-separated or list of ints)
    ADMIN_USER_IDS: str = "123456789,987654321"

    # Security & Networking
    SECRET_KEY: str = "evently_mvp_secret_key_change_in_production_32bytes"
    AUTH_DATE_MAX_AGE_SECONDS: int = 86400
    PUBLIC_HOST: Optional[str] = None
    APP_PUBLIC_HOST: Optional[str] = None
    CORS_ORIGINS: str = "*"

    # Broadcast Engine
    BROADCAST_RATE_LIMIT_PER_SEC: int = 25
    BROADCAST_FATIGUE_HOURS: int = 24
    BROADCAST_ATTRIBUTION_HOURS: int = 24
    FREE_BROADCASTS_PER_MONTH: int = 0
    PRO_BROADCASTS_PER_MONTH: int = 20

    # Storage Configuration (S3-compatible Object Storage or Persistent Local Volume)
    # Examples: Cloudflare R2, AWS S3, MinIO, Supabase S3, Yandex Object Storage
    STORAGE_BACKEND: str = "auto"
    STORAGE_ENDPOINT: Optional[str] = None
    STORAGE_BUCKET: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_KEY: Optional[str] = None
    STORAGE_REGION: str = "auto"
    STORAGE_PUBLIC_URL: Optional[str] = None

    # Standard S3 aliases
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_REGION_NAME: Optional[str] = None
    S3_PUBLIC_URL_PREFIX: Optional[str] = None

    # Local storage directory (supports Railway Volume mounts, e.g. /app/uploads or RAILWAY_VOLUME_MOUNT_PATH)
    STORAGE_LOCAL_DIR: Optional[str] = None

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
        "TELEGRAM_MINI_APP_SHORT_NAME",
        "ADMIN_USER_IDS",
        "SECRET_KEY",
        "PUBLIC_HOST",
        "APP_PUBLIC_HOST",
        "STORAGE_ENDPOINT",
        "STORAGE_BUCKET",
        "STORAGE_ACCESS_KEY",
        "STORAGE_SECRET_KEY",
        "STORAGE_PUBLIC_URL",
        "S3_ENDPOINT_URL",
        "S3_BUCKET_NAME",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "S3_PUBLIC_URL_PREFIX",
        "STORAGE_LOCAL_DIR",
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
        Resolves public HTTPS host for Telegram Webhook, Mini App, and image assets.
        Priority:
        1. settings.APP_PUBLIC_HOST or settings.PUBLIC_HOST
        2. RAILWAY_PUBLIC_DOMAIN (e.g. ivently.up.railway.app)
        3. RAILWAY_STATIC_URL
        4. Production fallback: https://ivently.up.railway.app (if APP_ENV == 'production')
        """
        host = (
            self.APP_PUBLIC_HOST
            or self.PUBLIC_HOST
            or os.getenv("APP_PUBLIC_HOST")
            or os.getenv("RAILWAY_PUBLIC_DOMAIN")
            or os.getenv("RAILWAY_STATIC_URL")
        )
        if not host:
            if self.APP_ENV == "production":
                return "https://ivently.up.railway.app"
            return None
        host = host.strip().strip("'\"").strip()
        if not host.startswith("http://") and not host.startswith("https://"):
            host = f"https://{host}"
        return host.rstrip("/")

    @property
    def clean_bot_username(self) -> str:
        """Returns sanitized Telegram bot username without '@' or whitespace."""
        u = (self.TELEGRAM_BOT_USERNAME or "Ivently_bot").strip().strip("'\"").lstrip("@")
        return u or "Ivently_bot"

    @property
    def effective_mini_app_url(self) -> str:
        """
        Resolves the Telegram Mini App launch URL.
        Priority:
        1. Explicit custom TELEGRAM_MINI_APP_URL if provided and different from default.
        2. Named Mini App direct link: https://t.me/<username>/<short_name> (if short_name configured).
        3. Main Mini App direct link: https://t.me/<username> (if short_name is empty).
        """
        custom_url = (self.TELEGRAM_MINI_APP_URL or "").strip().strip("'\"").strip()
        if custom_url and custom_url not in ("https://t.me/evently_bot/app", "https://t.me/Ivently_bot/app"):
            return custom_url

        short_name = (self.TELEGRAM_MINI_APP_SHORT_NAME or "").strip().strip("'\"").lstrip("/")
        if short_name:
            return f"https://t.me/{self.clean_bot_username}/{short_name}"
        return f"https://t.me/{self.clean_bot_username}"

    def get_event_deep_link(self, event_id: str, attribution_token: Optional[str] = None) -> str:
        """
        Returns official Telegram Mini App direct link with startapp parameter.
        Supports both named Mini App (https://t.me/<username>/<short_name>?startapp=...)
        and Main Mini App (https://t.me/<username>?startapp=...).
        When attribution_token is provided, appends '_b_{attribution_token}'.
        """
        base = self.effective_mini_app_url.split("?")[0].rstrip("/")
        if attribution_token:
            return f"{base}?startapp=event_{event_id}_b_{attribution_token}"
        return f"{base}?startapp=event_{event_id}"

    def get_organization_deep_link(self, org_id: str) -> str:
        """
        Returns official Telegram Mini App direct link for organization profile.
        Supports both named Mini App and Main Mini App.
        """
        base = self.effective_mini_app_url.split("?")[0].rstrip("/")
        return f"{base}?startapp=org_{org_id}"

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

    @property
    def effective_storage_endpoint(self) -> Optional[str]:
        return self.STORAGE_ENDPOINT or self.S3_ENDPOINT_URL

    @property
    def effective_storage_bucket(self) -> Optional[str]:
        return self.STORAGE_BUCKET or self.S3_BUCKET_NAME

    @property
    def effective_storage_access_key(self) -> Optional[str]:
        return self.STORAGE_ACCESS_KEY or self.S3_ACCESS_KEY_ID

    @property
    def effective_storage_secret_key(self) -> Optional[str]:
        return self.STORAGE_SECRET_KEY or self.S3_SECRET_ACCESS_KEY

    @property
    def effective_storage_region(self) -> str:
        return self.STORAGE_REGION or self.S3_REGION_NAME or "auto"

    @property
    def effective_storage_public_url(self) -> Optional[str]:
        pub = self.STORAGE_PUBLIC_URL or self.S3_PUBLIC_URL_PREFIX
        return pub.rstrip("/") if pub else None

    @property
    def is_s3_storage_configured(self) -> bool:
        """Checks if minimum required S3 credentials are provided."""
        return bool(
            self.effective_storage_bucket and
            self.effective_storage_access_key and
            self.effective_storage_secret_key
        )


settings = Settings()
