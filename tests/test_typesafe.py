import pytest
from app.services.typesafe import TypeSafeService


@pytest.mark.asyncio
async def test_typesafe_service_graceful_fallback_when_disabled():
    service = TypeSafeService(api_key=None, enabled=False)
    assert service.is_available() is False

    res = await service.verify_event_submission("Test Event", "Description here")
    assert res["is_valid"] is True
    assert res["source"] == "deterministic_fallback"


@pytest.mark.asyncio
async def test_typesafe_service_graceful_fallback_on_network_error():
    # Service with dummy key pointing to unreachable mock endpoint
    service = TypeSafeService(api_key="sk-test-key", enabled=True)
    service.endpoint = "http://127.0.0.1:59999/unreachable"
    service.timeout = 0.1  # Fast timeout

    res = await service.verify_event_submission("Test Event", "Description here")
    assert res["is_valid"] is True
    assert res["source"] == "deterministic_fallback"
