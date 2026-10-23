import pytest
from app.services.aggregator.city_mapping import validate_event_city, MTS_CITY_SLUGS
from app.services.aggregator.category_classifier import classify_event_category


def test_validate_event_city_anti_geo_spoofing():
    # 1. Padel tournament "Москва 2026" from msk.kassir.ru in Makhachkala MUST be rejected
    assert not validate_event_city(
        source_name="kassir",
        source_url="https://msk.kassir.ru/sport/dvorets-gimnastiki-irinyi-viner-usmanovoy/mejdunarodnyiy-turnir-po-padelu-moskva-2026-den-3_2026-10-25",
        title="Международный турнир по паделу «Москва 2026». День 4",
        venue_name="Дворец Ирины Винер",
        address="Центр города",
        target_city_id="makhachkala",
    )

    # 2. Real Makhachkala event on Yandex MUST be accepted
    assert validate_event_city(
        source_name="yandex_afisha",
        source_url="https://afisha.yandex.ru/makhachkala/theatre_show/sluga-dvukh-gospod-rus-dram-teatr-gorkogo",
        title="Слуга двух господ",
        venue_name="Русский драматический театр им. Горького",
        address="г. Махачкала, ул. Горького",
        target_city_id="makhachkala",
    )

    # 3. Yandex Afisha moscow URL in Makhachkala MUST be rejected
    assert not validate_event_city(
        source_name="yandex_afisha",
        source_url="https://afisha.yandex.ru/moscow/concert/polina-gagarina",
        title="Концерт Полины Гагариной",
        venue_name="Мегаспорт",
        address="Ходынский бульвар",
        target_city_id="makhachkala",
    )

    # 4. SPb Kassir URL in Saratov MUST be rejected
    assert not validate_event_city(
        source_name="kassir",
        source_url="https://spb.kassir.ru/koncert/skripka",
        title="Скрипичный концерт",
        venue_name="Филармония",
        address="г. Саратов",
        target_city_id="saratov",
    )

    # 5. MTS Live in Makhachkala MUST be rejected (not in verified active MTS cities)
    assert "makhachkala" not in MTS_CITY_SLUGS
    assert not validate_event_city(
        source_name="mts_live",
        source_url="https://live.mts.ru/moscow/announcements/concert",
        title="Концерт",
        venue_name="Клуб",
        address="Центр",
        target_city_id="makhachkala",
    )

    # 6. MTS Live in Moscow MUST be accepted
    assert validate_event_city(
        source_name="mts_live",
        source_url="https://live.mts.ru/moscow/announcements/concert-polina-gagarina",
        title="Концерт Полины Гагариной",
        venue_name="ВТБ Арена",
        address="г. Москва, Ленинградский проспект",
        target_city_id="moscow",
    )


def test_cinema_category_classification():
    # Cartoon with fairy tale words in cinema MUST be classified as 'cinema', NEVER 'theatre'
    cat1 = classify_event_category(
        title="Как Иван в сказку попал",
        description="В кино с 23 октября. Приключения сказочных героев.",
        venue_name="в 3 кинотеатрах",
        source_url="https://afisha.yandex.ru/voronezh/cinema/kak-ivan-v-skazku-popal",
    )
    assert cat1 == "cinema"

    # Animated movie in cinema
    cat2 = classify_event_category(
        title="Чудо-Юдо",
        description="Анимационный фильм в кинотеатре",
        venue_name="Кинотеатр Октябрь",
        source_url="https://afisha.yandex.ru/makhachkala/cinema/chudo-iudo-2026",
    )
    assert cat2 == "cinema"

    # Real Theatre play
    cat3 = classify_event_category(
        title="Слуга двух господ",
        description="Спектакль в драматическом театре",
        venue_name="Русский драматический театр им. Горького",
        source_url="https://afisha.yandex.ru/makhachkala/theatre_show/sluga-dvukh-gospod",
    )
    assert cat3 == "theatre"

    # Real Concert
    cat4 = classify_event_category(
        title="XCHO. Большой сольный концерт",
        description="Все хиты в живом исполнении",
        venue_name="Дом дружбы",
        source_url="https://afisha.yandex.ru/makhachkala/concert/xcho-12",
    )
    assert cat4 == "concerts"
