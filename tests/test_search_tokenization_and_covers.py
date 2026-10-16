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
    assert "photo-1514525253161-7a46d19cd819" in default_cover or default_cover.endswith("/covers/default_event.jpg")

    # Test dead Unsplash interception
    dead_url = "https://images.unsplash.com/photo-1520523839898-50712140e698?w=800"
    intercepted = resolve_absolute_image_url(dead_url)
    assert "photo-1514525253161-7a46d19cd819" in intercepted or intercepted.endswith("/covers/concerts.jpg")

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
    assert inline_res["type"] == "article"
    assert "photo-1514525253161-7a46d19cd819" in inline_res["thumbnail_url"] or inline_res["thumbnail_url"].endswith("/covers/default_event.jpg")
    assert "photo-1514525253161-7a46d19cd819" in inline_res["input_message_content"]["link_preview_options"]["url"] or inline_res["input_message_content"]["link_preview_options"]["url"].endswith("/covers/default_event.jpg")


@pytest.mark.asyncio
async def test_handle_inline_query_cache_time(test_session):
    """Verifies that handle_inline_query returns cache_time: 1 and is_personal: True."""
    res = await handle_inline_query(test_session, {"id": "test_q", "query": "чилл"})
    assert res["cache_time"] == 1
    assert res["is_personal"] is True


@pytest.mark.asyncio
async def test_inline_result_wsrv_and_html(test_session):
    """Verifies that locally hosted covers are proxied via wsrv.nl and messages use HTML parse_mode."""
    class MockUploadedEvent:
        id = "mock_uploaded_123"
        title = "Mock Festival"
        cover_image_url = "/uploads/covers/mock_test.jpg"
        venue_name = "Mock Stadium"
        city_name = "Москва"
        start_at = datetime.now(timezone.utc) + timedelta(days=1)
        price_amount = 1000.0
        is_free = False

    inline_res = build_event_inline_result(MockUploadedEvent())
    assert inline_res["type"] == "article"
    assert inline_res["title"].startswith("🎟 ")
    assert "wsrv.nl/?url=" in inline_res["thumbnail_url"]
    assert "w=160&h=160" in inline_res["thumbnail_url"]
    assert inline_res["input_message_content"]["parse_mode"] == "HTML"
    assert "<a href=" in inline_res["input_message_content"]["message_text"]
    assert inline_res["input_message_content"]["link_preview_options"]["show_above_text"] is True
