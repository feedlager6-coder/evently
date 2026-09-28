import pytest
from app.services.parser_service import parse_query


def test_parser_extracts_warsaw():
    res = parse_query("мероприятия в Варшаве")
    assert res.city_id == "warsaw"
    assert res.is_ambiguous is False

    res2 = parse_query("events in warsaw")
    assert res2.city_id == "warsaw"


def test_parser_extracts_makhachkala():
    res = parse_query("события в Махачкале")
    assert res.city_id == "makhachkala"
    assert res.is_ambiguous is False


def test_parser_extracts_moscow():
    res = parse_query("концерты в Москве")
    assert res.city_id == "moscow"
    assert res.category_id == "concerts"


def test_parser_extracts_categories():
    res_sport = parse_query("спорт в Варшаве")
    assert res_sport.category_id == "sports"

    res_party = parse_query("вечеринки в Москве")
    assert res_party.category_id == "parties"

    res_edu = parse_query("митап по разработке в Махачкале")
    assert res_edu.category_id == "education"

    res_biz = parse_query("бизнес нетворкинг в Варшаве")
    assert res_biz.category_id == "business"

    res_art = parse_query("выставки в Москве")
    assert res_art.category_id == "exhibitions"


def test_parser_extracts_dates():
    res_today = parse_query("мероприятия в Варшаве сегодня")
    assert res_today.date_filter == "today"

    res_tomorrow = parse_query("концерты завтра в Москве")
    assert res_tomorrow.date_filter == "tomorrow"

    res_weekend = parse_query("события на выходных в Махачкале")
    assert res_weekend.date_filter == "weekend"


def test_parser_handles_ambiguous_query():
    # Completely empty query without default city
    res_empty = parse_query("")
    assert res_empty.is_ambiguous is True
    assert res_empty.city_id is None

    # Unknown query with default city provided
    res_default = parse_query("что-нибудь интересное", default_city_id="warsaw")
    assert res_default.city_id == "warsaw"
    assert res_default.is_ambiguous is False
