import os
import sys
import time
import json
import hmac
import hashlib
from urllib.parse import urlencode
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.seeds.seed_data import seed_database

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_testtoken"


def make_test_init_data(
    user_id: int = 123456789,
    first_name: str = "Test",
    last_name: str = "User",
    username: str = "testuser",
    auth_date: int = None,
    bot_token: str = TEST_BOT_TOKEN,
    tamper_hash: bool = False,
    alter_user_after_hash: bool = False
) -> str:
    """Generates valid or intentionally corrupted Telegram initData for testing."""
    if auth_date is None:
        auth_date = int(time.time())

    user_dict = {
        "id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username
    }
    user_str = json.dumps(user_dict, separators=(",", ":"))

    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohC8P9_k",
        "user": user_str
    }

    # Data check string
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    # secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    sig_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if tamper_hash:
        sig_hash = "deadbeef" + sig_hash[8:]

    params["hash"] = sig_hash

    if alter_user_after_hash:
        params["user"] = json.dumps({"id": 999999999, "first_name": "Hacker"})

    return urlencode(params)


@pytest_asyncio.fixture(scope="function")
async def test_session():
    """Provides an isolated in-memory async SQLite session with seeded demo data."""
    test_engine = create_async_engine(TEST_DB_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )

    async with TestSessionLocal() as session:
        await seed_database(session)
        yield session

    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_session):
    """Provides an async HTTP client configured with the test database dependency override."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
