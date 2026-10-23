import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.services.aggregator.yandex_afisha_parser import parse_russian_date_time, YandexAfishaParser
from app.services.event_service import resolve_city_timezone


def test_parse_russian_date_time():
    tz = resolve_city_timezone("Europe/Moscow")
    dt = parse_russian_date_time("27 октября", "18:30", tz)
    assert dt is not None
    # In Europe/Moscow (UTC+3), 18:30 is 15:30 UTC
    assert dt.day == 27
    assert dt.month == 10
    assert dt.hour == 15
    assert dt.minute == 30

    dt_korol = parse_russian_date_time("24 октября", "17:00", tz)
    assert dt_korol is not None
    assert dt_korol.day == 24
    assert dt_korol.month == 10
    assert dt_korol.hour == 14
    assert dt_korol.minute == 0


def test_yandex_cinema_rejection():
    # Should reject cinema URL
    mock_html = """
    <script>
    window['__APOLLO_STATE__'] = {
        "EventPreview:c1": {
            "__typename": "EventPreview",
            "id": "c1",
            "url": "/makhachkala/cinema/chudo-iudo",
            "title": "Чудо-Юдо",
            "contentRating": "6+",
            "argument": "Мультфильм в кинотеатрах"
        }
    };
    </script>
    """
    events = YandexAfishaParser._parse_apollo_state(mock_html, default_city_id="makhachkala")
    assert len(events) == 0
