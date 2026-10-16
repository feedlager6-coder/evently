import pytest
from app.services.external_sync_service import resolve_category


def test_fatima_play_resolved_to_theatre():
    # Test culture.ru title typo "Спекталь «Фатима»" at Kumyk Theatre
    res = resolve_category(
        raw_cat="",
        title="Спекталь «Фатима»",
        description="Постановка по поэме К. Хетагурова",
        venue_name="Кумыкский театр им. А.-П. Салаватова"
    )
    assert res == "theatre"


def test_language_festival_resolved_to_education():
    # Test festival in library with "язык как отражение истории"
    res = resolve_category(
        raw_cat="",
        title="Фестиваль «Язык как отражение истории и инструмент культуры»",
        description="Лекции и круглые столы, посвященные языкам Дагестана",
        venue_name="Национальная библиотека Республики Дагестан им. Р. Гамзатова"
    )
    assert res == "education"


def test_sports_never_matches_culture_or_literature():
    # Ensure words with root "тур" like "культура", "литература" NEVER match sports
    res_culture = resolve_category(
        raw_cat="",
        title="Калейдоскоп культур",
        description="Знакомство с обычаями народов региона",
        venue_name="Ставропольское краевое училище дизайна"
    )
    assert res_culture != "sports"

    res_concert_culture = resolve_category(
        raw_cat="",
        title="Концерт «День культуры и языков народов Дагестана»",
        description="Праздничный концерт воспитанников школы искусств",
        venue_name="Детская школа искусств им. С. Агабабова г. Каспийска"
    )
    assert res_concert_culture == "concerts"

    res_lermontov = resolve_category(
        raw_cat="",
        title="«Историко-культурная концепция М.Ю. Лермонтова»",
        description="Лекция в музее",
        venue_name="Государственный музей-заповедник М. Ю. Лермонтова"
    )
    assert res_lermontov != "sports"


def test_genuine_sports_matches_sports():
    res_excursion = resolve_category(
        raw_cat="",
        title="Экскурсия «Форт № 1»",
        description="Пешеходный маршрут по оборонительным сооружениям",
        venue_name="Форт № 1"
    )
    assert res_excursion == "sports"

    res_tourist = resolve_category(
        raw_cat="",
        title="Программа «Туристическими тропами Кабардино-Балкарии»",
        description="Поход по горным маршрутам",
        venue_name="Центр туризма"
    )
    assert res_tourist == "sports"

    res_quest = resolve_category(
        raw_cat="",
        title="Городской квест «Тайны старого города»",
        description="Спортивно-интеллектуальный забег по станциям",
        venue_name="Центральный парк"
    )
    assert res_quest == "sports"


def test_exhibitions_priority():
    res_exhibition = resolve_category(
        raw_cat="",
        title="Выставка «Живопись Кавказа»",
        description="Экспозиция работ современных художников",
        venue_name="Музей изобразительных искусств"
    )
    assert res_exhibition == "exhibitions"


def test_theatre_in_venue_with_exhibition_title():
    # If exhibition is held in a theatre hall, it should remain exhibition, not theatre
    res = resolve_category(
        raw_cat="",
        title="Выставка эскизов театральных костюмов",
        description="Экспозиция в фойе",
        venue_name="Новосибирский академический театр оперы и балета (НОВАТ)"
    )
    assert res == "exhibitions"


def test_potpourri_about_dagestan_resolved_to_concerts():
    # Test "Попурри о Дагестане" with description containing "картины" and venue "ансамбль"
    res = resolve_category(
        raw_cat="",
        title="«Попурри о Дагестане»",
        description="В программе 7- «Пьесы - картины» М. Кажлаева, народные мелодии и хореографические номера",
        venue_name="Государственный ансамбль песни и танца «Дагестан»"
    )
    assert res == "concerts"


def test_musical_forms_resolved_to_concerts():
    assert resolve_category(title="Соната № 14 для фортепиано", venue_name="Концертный зал") == "concerts"
    assert resolve_category(title="Сюита в старинном стиле", venue_name="Дом музыки") == "concerts"
    assert resolve_category(title="Торжественная увертюра", venue_name="Филармония") == "concerts"

