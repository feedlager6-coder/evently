import pytest
from app.config import settings


@pytest.mark.asyncio
async def test_yandex_verification_missing_env(client, monkeypatch):
    """
    Requirement 4 & 11:
    When YANDEX_VERIFICATION_CODE is absent/empty:
    - Route returns neutral 404 Not Found;
    - Response body is neutral ("Verification unavailable");
    - Does not reveal internal data or placeholders.
    """
    monkeypatch.setattr(settings, "YANDEX_VERIFICATION_CODE", None)

    resp = await client.get("/verification/yandex")
    assert resp.status_code == 404
    assert "Verification unavailable" in resp.text
    # Ensure no internal keys or placeholders are leaked
    assert "placeholder" not in resp.text.lower()
    assert "token" not in resp.text.lower()
    assert "secret" not in resp.text.lower()


@pytest.mark.asyncio
async def test_yandex_verification_configured_env(client, monkeypatch):
    """
    Requirement 5 & 11:
    When YANDEX_VERIFICATION_CODE is set:
    - Returns HTTP 200;
    - Returns ONLY the verification code as plain text;
    - Response content-type is text/plain;
    - No cookies are set;
    - Unauthenticated request works;
    - No Telegram initData required.
    """
    dummy_code = "mock_yandex_verification_code_abc123"
    monkeypatch.setattr(settings, "YANDEX_VERIFICATION_CODE", dummy_code)

    resp = await client.get("/verification/yandex")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    assert resp.text == dummy_code
    assert "set-cookie" not in resp.headers


@pytest.mark.asyncio
async def test_yandex_verification_strips_whitespace(client, monkeypatch):
    """
    Ensures leading/trailing whitespace or accidental quotes in env variable are stripped cleanly.
    """
    padded_code = "  mock_padded_code_xyz789  "
    monkeypatch.setattr(settings, "YANDEX_VERIFICATION_CODE", padded_code)

    resp = await client.get("/verification/yandex")
    assert resp.status_code == 200
    assert resp.text == "mock_padded_code_xyz789"


@pytest.mark.asyncio
async def test_yandex_verification_trailing_slash_support(client, monkeypatch):
    """
    Ensures crawler accessing /verification/yandex/ (with trailing slash) also gets HTTP 200.
    """
    dummy_code = "mock_slash_support_code_456"
    monkeypatch.setattr(settings, "YANDEX_VERIFICATION_CODE", dummy_code)

    resp = await client.get("/verification/yandex/")
    assert resp.status_code == 200
    assert resp.text == dummy_code


@pytest.mark.asyncio
async def test_yandex_verification_does_not_leak_other_envs(client, monkeypatch):
    """
    Requirement 11:
    Route does NOT reveal other secrets, environment variables, or tokens.
    """
    dummy_code = "sample_test_code_unique"
    monkeypatch.setattr(settings, "YANDEX_VERIFICATION_CODE", dummy_code)

    resp = await client.get("/verification/yandex")
    assert resp.status_code == 200
    # Must not contain any sensitive values from settings
    assert settings.SECRET_KEY not in resp.text
    assert settings.TELEGRAM_BOT_TOKEN not in resp.text
    assert settings.DATABASE_URL not in resp.text
    assert settings.ADMIN_USER_IDS not in resp.text


@pytest.mark.asyncio
async def test_verification_path_isolation_from_spa(client):
    """
    Requirement 7:
    Ensures verification paths are never captured by SPA fallback serving index.html.
    """
    resp = await client.get("/verification/unknown-endpoint")
    assert resp.status_code == 404
    assert "<!DOCTYPE html>" not in resp.text
    assert '<div id="root">' not in resp.text
