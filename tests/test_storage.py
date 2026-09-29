import io
import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.services.storage_service import StorageService, storage_service
from tests.conftest import make_test_init_data


# Minimal valid image payloads
TINY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9"
TINY_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
TINY_WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0e\x00\x00\x00/\x00\x00\x00\x00\x07\x88\x85%`\x00\x00\x00"


def test_magic_bytes_validation():
    service = StorageService()

    # Valid images
    assert service.validate_image(TINY_JPEG, "image/jpeg") == ".jpg"
    assert service.validate_image(TINY_PNG, "image/png") == ".png"
    assert service.validate_image(TINY_WEBP, "image/webp") == ".webp"

    # Invalid MIME type
    with pytest.raises(HTTPException) as exc:
        service.validate_image(TINY_JPEG, "application/pdf")
    assert exc.value.status_code == 400
    assert "Unsupported image type" in exc.value.detail

    # Spoofed extension / fake bytes (text disguised as JPEG)
    with pytest.raises(HTTPException) as exc:
        service.validate_image(b"<!DOCTYPE html><html>", "image/jpeg")
    assert exc.value.status_code == 400
    assert "Invalid image format" in exc.value.detail

    # File size exceeding 5MB
    large_payload = TINY_JPEG + (b"\x00" * (5 * 1024 * 1024 + 1))
    with pytest.raises(HTTPException) as exc:
        service.validate_image(large_payload, "image/jpeg")
    assert exc.value.status_code == 400
    assert "File exceeds maximum allowed size" in exc.value.detail


@pytest.mark.asyncio
async def test_save_image_local():
    service = StorageService()
    url = await service.save_image(TINY_PNG, "image/png", folder="test_folder")
    assert url.startswith("/uploads/test_folder/")
    assert url.endswith(".png")


@pytest.mark.asyncio
async def test_upload_avatar_endpoint(client: AsyncClient):
    """Verifies POST /api/v1/organizations/upload-avatar endpoint."""
    files = {"file": ("avatar.png", TINY_PNG, "image/png")}
    response = await client.post("/api/v1/organizations/upload-avatar", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "avatars" in data["url"]

    # Test upload with invalid file format
    invalid_files = {"file": ("avatar.txt", b"plain text", "text/plain")}
    err_response = await client.post("/api/v1/organizations/upload-avatar", files=invalid_files)
    assert err_response.status_code == 400


@pytest.mark.asyncio
async def test_upload_event_cover_endpoint(client: AsyncClient):
    """Verifies POST /api/v1/events/upload-cover endpoint requires auth and works with valid image."""
    init_data = make_test_init_data(user_id=123456789)
    headers = {"X-Telegram-Init-Data": init_data}

    # Upload valid JPEG cover
    files = {"file": ("cover.jpg", TINY_JPEG, "image/jpeg")}
    response = await client.post("/api/v1/events/upload-cover", files=files, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "covers" in data["url"]

    # Upload malicious fake file
    fake_files = {"file": ("hack.jpg", b"fake binary payload", "image/jpeg")}
    err_response = await client.post("/api/v1/events/upload-cover", files=fake_files, headers=headers)
    assert err_response.status_code == 400


@pytest.mark.asyncio
async def test_health_check_storage_diagnostics(client: AsyncClient):
    """Verifies that /health safely reports storage diagnostics without secrets."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "storage" in data
    storage_info = data["storage"]
    assert "backend" in storage_info
    assert "persistent" in storage_info
    assert storage_info["backend"] in ("s3", "railway_volume", "ephemeral_container")
    # Verify no credentials leaked
    assert "secret" not in str(storage_info).lower()
    assert "token" not in str(storage_info).lower()
    assert "password" not in str(storage_info).lower()
