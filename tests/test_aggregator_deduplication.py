import pytest
from datetime import datetime, timezone, timedelta

from app.services.aggregator.deduplication import (
    normalize_event_title,
    normalize_venue,
    calculate_title_similarity,
    is_cross_platform_duplicate,
)
from app.services.aggregator.category_classifier import classify_event_category
from app.services.aggregator.city_mapping import resolve_city_from_text


# --- 1. TITLE & VENUE NORMALIZATION TESTS ---

def test_normalize_event_title():
    # Strips noise words, age ratings, quotes, cities
    t1 = "«Баста. Большой сольный концерт» 16+"
    assert normalize_event_title(t1) == "баста"

    t2 = "Концерт Басты в Махачкале 12+"
    assert normalize_event_title(t2) == "баста"

    t3 = "Шура. Старые песни о главном (Live 18+)"
    # 'концерт', 'песни' are noise, 'старые', 'главном' remain
    assert "шура" in normalize_event_title(t3)

    t4 = "Юбилейный концерт группы «Рок-Острова»"
    assert "рок" in normalize_event_title(t4) and "остров" in normalize_event_title(t4)

    t5 = "МОТ. Презентация нового альбома в Москве"
    assert "мот" in normalize_event_title(t5)


def test_normalize_venue():
    v1 = "Дворец спорта им. Али Алиева"
    v2 = "ДС им. Али Алиева"
    v3 = "Дворец спорта имени Али Алиева"
    v4 = "Спортивный комплекс «Али Алиева»"

    assert normalize_venue(v1) == "али алиева"
    assert normalize_venue(v2) == "али алиева"
    assert normalize_venue(v3) == "али алиева"
    assert "али алиева" in normalize_venue(v4)

    # Cultural venues
    c1 = "Концертный зал «Москва»"
    c2 = "КЗ «Москва»"
    assert normalize_venue(c1) == "москва"
    assert normalize_venue(c2) == "москва"


# --- 2. BASTA CROSS-PLATFORM DEDUPLICATION BENCHMARK ---

def test_basta_cross_platform_deduplication():
    """
    Direct benchmark test from requirement:
    - Kassir: «Баста. Большой сольный концерт» | 15 ноября 19:00 | Дворец спорта им. Али Алиева
    - MTS Live: «Баста» | 15 ноября 19:00 | ДС им. Али Алиева
    - Yandex: «Концерт Басты в Махачкале» | 15 ноября 19:00 | Дворец спорта имени Али Алиева
    All three must pair-wise match as duplicates in the same city and date!
    """
    event_time = datetime(2026, 11, 15, 19, 0, 0, tzinfo=timezone.utc)
    city = "makhachkala"

    kassir = {
        "title": "«Баста. Большой сольный концерт»",
        "venue": "Дворец спорта им. Али Алиева",
        "time": event_time,
        "city": city,
    }
    mts = {
        "title": "«Баста»",
        "venue": "ДС им. Али Алиева",
        "time": event_time,
        "city": city,
    }
    yandex = {
        "title": "«Концерт Басты в Махачкале»",
        "venue": "Дворец спорта имени Али Алиева",
        "time": event_time,
        "city": city,
    }

    # 1. Kassir <=> MTS Live
    is_dup_km, score_km, reason_km = is_cross_platform_duplicate(
        title_a=kassir["title"], venue_a=kassir["venue"], time_a=kassir["time"], city_a=kassir["city"],
        title_b=mts["title"], venue_b=mts["venue"], time_b=mts["time"], city_b=mts["city"],
    )
    assert is_dup_km is True, f"Kassir-MTS should be duplicate: {reason_km}"
    assert score_km >= 0.85

    # 2. Kassir <=> Yandex.Afisha
    is_dup_ky, score_ky, reason_ky = is_cross_platform_duplicate(
        title_a=kassir["title"], venue_a=kassir["venue"], time_a=kassir["time"], city_a=kassir["city"],
        title_b=yandex["title"], venue_b=yandex["venue"], time_b=yandex["time"], city_b=yandex["city"],
    )
    assert is_dup_ky is True, f"Kassir-Yandex should be duplicate: {reason_ky}"
    assert score_ky >= 0.80

    # 3. MTS Live <=> Yandex.Afisha
    is_dup_my, score_my, reason_my = is_cross_platform_duplicate(
        title_a=mts["title"], venue_a=mts["venue"], time_a=mts["time"], city_a=mts["city"],
        title_b=yandex["title"], venue_b=yandex["venue"], time_b=yandex["time"], city_b=yandex["city"],
    )
    assert is_dup_my is True, f"MTS-Yandex should be duplicate: {reason_my}"
    assert score_my >= 0.80


# --- 3. EDGE CASES & NON-DUPLICATES ---

def test_different_artists_same_venue_not_duplicate():
    event_time = datetime(2026, 11, 15, 19, 0, 0, tzinfo=timezone.utc)
    is_dup, score, reason = is_cross_platform_duplicate(
        title_a="Баста", venue_a="ДС им. Али Алиева", time_a=event_time, city_a="makhachkala",
        title_b="Хаски", venue_b="ДС им. Али Алиева", time_b=event_time, city_b="makhachkala",
    )
    assert is_dup is False
    assert score <= 0.65


def test_same_artist_different_days_not_duplicate():
    time1 = datetime(2026, 11, 15, 19, 0, 0, tzinfo=timezone.utc)
    time2 = datetime(2026, 11, 16, 19, 0, 0, tzinfo=timezone.utc)  # 24h later
    is_dup, score, reason = is_cross_platform_duplicate(
        title_a="Баста", venue_a="ДС им. Али Алиева", time_a=time1, city_a="makhachkala",
        title_b="Баста", venue_b="ДС им. Али Алиева", time_b=time2, city_b="makhachkala",
    )
    assert is_dup is False
    assert "Time difference" in reason


def test_same_event_different_cities_not_duplicate():
    event_time = datetime(2026, 11, 15, 19, 0, 0, tzinfo=timezone.utc)
    is_dup, score, reason = is_cross_platform_duplicate(
        title_a="Баста", venue_a="ВТБ Арена", time_a=event_time, city_a="moscow",
        title_b="Баста", venue_b="ДС им. Али Алиева", time_b=event_time, city_b="makhachkala",
    )
    assert is_dup is False
    assert reason == "Different cities"


# --- 4. SMART 2-TIER CATEGORY CLASSIFIER TESTS ---

def test_category_classifier_standup_humor():
    # Standup MUST map to 'parties' (never 'theatre', never 'concerts')
    assert classify_event_category("Большой сольный Stand Up концерт Павла Воли") == "parties"
    assert classify_event_category("Открытый микрофон в баре") == "parties"
    assert classify_event_category("Стендап на крыше") == "parties"
    assert classify_event_category("Шоу импровизация комиков") == "parties"
    assert classify_event_category("Прожарка звёзд КВН") == "parties"


def test_category_classifier_kids_family():
    # Children/Family MUST map to 'other' (or 'theatre' if explicitly a play; never 'concerts')
    assert classify_event_category("Шоу мыльных пузырей и иллюзионист") == "other"
    assert classify_event_category("Интерактивное шоу «Три кота» для детей") == "other"
    assert classify_event_category("Большой новогодний цирк") == "other"
    assert classify_event_category("Мультконцерт «Синий трактор»") == "other"
    # Fairytale theatre play
    assert classify_event_category("Детский спектакль «Сказка о царе Салтане»") == "theatre"
    assert classify_event_category("Кукольный спектакль для малышей") == "theatre"


def test_category_classifier_theatre():
    # Theatre & Classical Drama
    assert classify_event_category("Спектакль «Мастер и Маргарита»") == "theatre"
    assert classify_event_category("Балет «Лебединое озеро»") == "theatre"
    assert classify_event_category("Опера «Евгений Онегин»") == "theatre"
    assert classify_event_category("Мюзикл «Призрак Оперы»") == "theatre"
    assert classify_event_category("Комедия «Любовь и голуби»") == "theatre"
    assert classify_event_category("Драма в двух действиях") == "theatre"


def test_category_classifier_sports():
    assert classify_event_category("Матч «Спартак» — «Динамо»") == "sports"
    assert classify_event_category("Чемпионат России по вольной борьбе") == "sports"
    assert classify_event_category("Турнир ММА: Битва на Кавказе") == "sports"
    assert classify_event_category("Хоккейный матч КХЛ") == "sports"
    assert classify_event_category("Московский марафон 2026") == "sports"


def test_category_classifier_exhibitions():
    assert classify_event_category("Выставка шедевров Третьяковской галереи") == "exhibitions"
    assert classify_event_category("Экспозиция современной живописи") == "exhibitions"
    assert classify_event_category("Музей оптических иллюзий") == "exhibitions"
    assert classify_event_category("Вернисаж дагестанских художников") == "exhibitions"


def test_category_classifier_education_and_business():
    assert classify_event_category("Лекция «История древнего Дербента»") == "education"
    assert classify_event_category("Мастер-класс по живописи маслом") == "education"
    assert classify_event_category("Бизнес-форум лидеров IT-индустрии") == "business"
    assert classify_event_category("Конференция по стартапам и инвестициям") == "business"


def test_category_classifier_concerts_music():
    assert classify_event_category("Концерт группы «Руки Вверх!»") == "concerts"
    assert classify_event_category("Симфонический оркестр: музыка Ханса Циммера") == "concerts"
    assert classify_event_category("Вечер джаза в клубе") == "concerts"
    assert classify_event_category("Рок-фестиваль под открытым небом") == "concerts"
    assert classify_event_category("Неоклассика при свечах в старинном соборе") == "concerts"


def test_category_classifier_rubric_fallback():
    # If title is completely abstract (e.g. "Затмение"), rubric fallback resolves it
    assert classify_event_category("Затмение", raw_rubric="theatre") == "theatre"
    assert classify_event_category("Затмение", raw_rubric="concert") == "concerts"
    assert classify_event_category("Затмение", raw_rubric="standup") == "parties"
    assert classify_event_category("Затмение", raw_rubric="sport") == "sports"
    assert classify_event_category("Затмение", raw_rubric="exhibitions") == "exhibitions"


# --- 5. CITY TEXT RESOLUTION TESTS ---

def test_resolve_city_from_text():
    assert resolve_city_from_text("г. Махачкала, проспект Гамзатова 12") == "makhachkala"
    assert resolve_city_from_text("Дербентская крепость Нарын-Кала, Дербент") == "derbent"
    assert resolve_city_from_text("Москва, ул. Тверская 15") == "moscow"
    assert resolve_city_from_text("Санкт-Петербург, Невский пр. 28") == "spb"
    assert resolve_city_from_text("Неизвестный адрес", default_city_id="sochi") == "sochi"

# --- 6. PARSER EXTRACTION LOGIC TESTS ---

def test_kassir_parser_mock_extraction():
    from app.services.aggregator.kassir_parser import KassirParser

    # Mock Nuxt 3 SSR data payload
    mock_nuxt = """
    <script id="__NUXT_DATA__" type="application/json">
    [
        ["ShallowReactive", 1],
        {
            "id": "1001",
            "title": 2,
            "description": 3,
            "beginsAt": 4,
            "venueName": 5,
            "venue": {"name": 5, "address": {"addressString": 6}},
            "posterImage": 7,
            "priceRange": {"min": 8, "max": 9},
            "ageGroup": 10,
            "url": 11
        },
        "Большой сольный концерт Басты",
        "Легендарный рэпер выступит с главными хитами",
        "2026-11-20T19:00:00+03:00",
        "ВТБ Арена",
        "Ленинградский просп., 36",
        "https://cdn.kassir.ru/poster/basta.jpg",
        2000,
        15000,
        "16+",
        "https://msk.kassir.ru/koncert/basta-vtb"
    ]
    </script>
    """
    events = KassirParser._parse_nuxt_data(mock_nuxt, default_city_id="moscow", base_url="https://msk.kassir.ru")
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "Большой сольный концерт Басты"
    assert ev.venue_name == "ВТБ Арена"
    assert ev.price_min == 2000.0
    assert ev.price_max == 15000.0
    assert ev.age_restriction == "16+"
    assert ev.category_id == "concerts"
    assert ev.source_name == "kassir"
    assert ev.source_url == "https://msk.kassir.ru/koncert/basta-vtb"


def test_mts_live_parser_mock_extraction():
    from app.services.aggregator.mts_live_parser import MtsLiveParser

    # Mock Next.js streaming RSC push chunk
    mock_html = r'''
    <script>
    self.__next_f.push([1,"20:[\"$\",\"$L61\",null,{\"announcementCollection\":{\"id\":4,\"title\":\"Концерты\",\"items\":[{\"id\":998877,\"title\":\"Концерт Zivert\",\"alias\":\"zivert-show\",\"url\":\"/moscow/announcements/zivert-show\",\"imageUrl\":\"https://live.mts.ru/image/zivert.jpg\",\"eventMinPrice\":3500,\"eventClosestDateTime\":\"2026-12-05T20:00:00\",\"venue\":{\"id\":123,\"title\":\"VK Stadium\"}}]}}]\n"]);
    </script>
    '''
    events = MtsLiveParser._parse_rsc_payload(mock_html, default_city_id="moscow")
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "Концерт Zivert"
    assert ev.venue_name == "VK Stadium"
    assert ev.price_min == 3500.0
    assert ev.source_name == "mts_live"
    assert ev.source_url == "https://live.mts.ru/moscow/announcements/zivert-show"
    assert ev.category_id == "concerts"


def test_yandex_afisha_parser_mock_extraction():
    from app.services.aggregator.yandex_afisha_parser import YandexAfishaParser

    # Mock Apollo Client State script
    mock_html = """
    <script>
    window['__APOLLO_STATE__'] = {
        "Ticket:t1": {
            "__typename": "Ticket",
            "id": "t1",
            "price": {"__typename": "TicketPriceRange", "currency": "rub", "min": 180000, "max": 600000}
        },
        "Featured:f1": {
            "__typename": "Featured",
            "id": "f1",
            "object": {
                "__typename": "ActualEvent",
                "event": {"__ref": "EventPreview:e1"},
                "scheduleInfo": {
                    "__typename": "EventScheduleInfo",
                    "placePreview": "Театр на Бронной",
                    "regularity": {"__typename": "Regularity", "singleShowtime": "2026-11-25T19:00:00"}
                }
            }
        },
        "EventPreview:e1": {
            "__typename": "EventPreview",
            "id": "e1",
            "url": "/moscow/theatre_show/optimisty",
            "title": "Спектакль «Оптимисты»",
            "contentRating": "18+",
            "argument": "Новая яркая постановка",
            "image": {
                "__typename": "Image",
                "image({\\"size\\":\\"origin\\"})": {"url": "https://avatars.mds.yandex.net/orig.jpg"}
            },
            "tickets": [{"__ref": "Ticket:t1"}]
        }
    };
    </script>
    """
    events = YandexAfishaParser._parse_apollo_state(mock_html, default_city_id="moscow", default_rubric="theatre")
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "Спектакль «Оптимисты»"
    assert ev.venue_name == "Театр на Бронной"
    assert ev.price_min == 1800.0  # 180000 kopecks / 100
    assert ev.source_name == "yandex_afisha"
    assert ev.source_url == "https://afisha.yandex.ru/moscow/theatre_show/optimisty"
    assert ev.category_id == "theatre"
    assert ev.age_restriction == "18+"


def test_same_day_multi_session_deduplicated():
    """Verify that multiple sessions of the same show on the same day in the same city are deduplicated."""
    time_15_00 = datetime(2026, 10, 23, 15, 0, 0, tzinfo=timezone.utc)
    time_18_45 = datetime(2026, 10, 23, 18, 45, 0, tzinfo=timezone.utc)

    is_dup, score, reason = is_cross_platform_duplicate(
        title_a="Стендап-экскурсия по Санкт-Петербургу",
        venue_a="Памятник Конке",
        time_a=time_15_00,
        city_a="spb",
        title_b="Стендап-экскурсия по Санкт-Петербургу",
        venue_b="Памятник Сергею Довлатову",
        time_b=time_18_45,
        city_b="spb",
    )
    assert is_dup is True
    assert score >= 0.75

    # Tver quizzes
    tver_12_30 = datetime(2026, 10, 30, 12, 30, 0, tzinfo=timezone.utc)
    tver_17_00 = datetime(2026, 10, 30, 17, 0, 0, tzinfo=timezone.utc)
    is_dup_tver, score_tver, _ = is_cross_platform_duplicate(
        title_a="Детский мини-квиз",
        venue_a='Котокафе "Мур-мяу"',
        time_a=tver_12_30,
        city_a="tver",
        title_b="Детский мини-квиз",
        venue_b='Котокафе "Мур-мяу"',
        time_b=tver_17_00,
        city_b="tver",
    )
    assert is_dup_tver is True
    assert score_tver >= 0.75


def test_enhanced_category_classifier_cases():
    """Verify that artist names, exhibitions, workshops and tours don't fall into 'other'."""
    # Music & Concerts
    assert classify_event_category("Леша Свик. Все хиты!") == "concerts"
    assert classify_event_category("Максим Фадеев", venue_name="Live Арена") == "concerts"
    assert classify_event_category("t.A.T.u", venue_name="VK Stadium") == "concerts"
    assert classify_event_category("Группа ПЕЛАГЕЯ") == "concerts"
    assert classify_event_category("СУПЕРДИСКОТЕКА 90-Х РАДИО РЕКОРД") in ["concerts", "parties"]

    # Exhibitions
    assert classify_event_category("Пабло Пикассо. Метаморфозы", venue_name="Музей изобразительных искусств") == "exhibitions"
    assert classify_event_category("Иммерсивная выставка «Сад сновидений»") == "exhibitions"
    assert classify_event_category("Экспозиция в Эрмитаже", venue_name="Государственный Эрмитаж") == "exhibitions"

    # Education / Workshops / Tours
    assert classify_event_category("Мастер-класс по керамике") == "education"
    assert classify_event_category("Стендап-экскурсия по Санкт-Петербургу") == "parties"  # standup keyword priority
    assert classify_event_category("Пешеходная экскурсия по старому городу") == "education"
    assert classify_event_category("Детский мини-квиз") == "education"
    assert classify_event_category("Цикл занятий «Сказкины объятия»", venue_name="Детская библиотека") == "education"

    # Theatre
    assert classify_event_category("Слуга двух господ", venue_name="Русский драматический театр им. Горького") == "theatre"
    assert classify_event_category("Сказка о Белоснежке и семи гномах") == "theatre"

