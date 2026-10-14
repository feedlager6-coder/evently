import pytest
from app.services.event_service import list_published_events
from app.models.event import Event, EventStatus
from app.services.telegram_bot import handle_inline_query, build_event_inline_result, resolve_absolute_image_url
from datetime import datetime, timezone, timedelta

@pytest.mark.asyncio
async def test_tokenized_search_query_hyphen_and_case(test_session):
    """Verifies that search_query splits hyphens and matches Cyrillic regardless of case."""
    now = datetime.now(timezone.utc)
    ev = Event(
        id="test_chill_999",
        title="ЧИЛЛ ЧИЛЛ",
        description="Отдыхаем на природе",
        category_id="concerts",
        city_id="makhachkala",
        start_at=now + timedelta(days=2),
        venue_name="Дача",
        address="ул. Ленина 1, Махачкала",
        organizer_user_id=12345,
        price_amount=0,
        status=EventStatus.PUBLISHED.value
    )
    test_session.add(ev)
    await test_session.commit()

    # 1. Search with hyphen
    events, total = await list_published_events(test_session, search_query="Чилл-Чилл")
    assert total >= 1
    assert any(e.id == ev.id for e in events)

    # 2. Search lowercase
    events, total = await list_published_events(test_session, search_query="чилл")
    assert total >= 1
    assert any(e.id == ev.id for e in events)


@pytest.mark.asyncio
async def test_inline_result_fallback_covers(test_session):
    """Verifies that events with NULL or dead Unsplash covers receive valid JPEG covers."""
    # Test resolve_absolute_image_url fallback
    default_cover = resolve_absolute_image_url(None)
    assert default_cover.endswith("/covers/default_event.jpg")

    # Test dead Unsplash interception
    dead_url = "https://images.unsplash.com/photo-1520523839898-50712140e698?w=800"
    intercepted = resolve_absolute_image_url(dead_url)
    assert intercepted.endswith("/covers/concerts.jpg")

    # Test inline result creation for NULL cover
    class MockEvent:
        id = "mock_123"
        title = "Mock Concert"
        cover_image_url = None
        venue_name = "Mock Venue"
        city_name = "Москва"
        start_at = datetime.now(timezone.utc) + timedelta(days=1)
        price_amount = 500.0
        is_free = False

    inline_res = build_event_inline_result(MockEvent())
    assert inline_res["type"] == "photo"
    assert inline_res["photo_url"].endswith("/covers/default_event.jpg")
    assert inline_res["thumbnail_url"].endswith("/covers/default_event.jpg")


@pytest.mark.asyncio
async def test_handle_inline_query_cache_time(test_session):
    """Verifies that handle_inline_query returns cache_time: 5 and is_personal: True."""
    res = await handle_inline_query(test_session, {"id": "test_q", "query": "чилл"})
    assert res["cache_time"] == 5
    assert res["is_personal"] is True
