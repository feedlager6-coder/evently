import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.city import City
from app.models.category import Category
from app.models.user import User
from app.models.event import Event, EventStatus

logger = logging.getLogger("evently.seeds")

CITIES_DATA = [
    {
        "id": "makhachkala",
        "name": "Махачкала",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 42.9849,
        "longitude": 47.5047,
        "is_active": True
    },
    {
        "id": "moscow",
        "name": "Москва",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 55.7558,
        "longitude": 37.6173,
        "is_active": True
    },
    {
        "id": "spb",
        "name": "Санкт-Петербург",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 59.9343,
        "longitude": 30.3351,
        "is_active": True
    },
    {
        "id": "kazan",
        "name": "Казань",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 55.7961,
        "longitude": 49.1064,
        "is_active": True
    },
    {
        "id": "krasnodar",
        "name": "Краснодар",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 45.0355,
        "longitude": 38.9753,
        "is_active": True
    },
    {
        "id": "rostov_on_don",
        "name": "Ростов-на-Дону",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 47.2357,
        "longitude": 39.7015,
        "is_active": True
    },
    {
        "id": "yekaterinburg",
        "name": "Екатеринбург",
        "country": "Россия",
        "timezone": "Asia/Yekaterinburg",
        "currency": "RUB",
        "latitude": 56.8389,
        "longitude": 60.6057,
        "is_active": True
    },
    {
        "id": "novosibirsk",
        "name": "Новосибирск",
        "country": "Россия",
        "timezone": "Asia/Novosibirsk",
        "currency": "RUB",
        "latitude": 55.0084,
        "longitude": 82.9357,
        "is_active": True
    },
    {
        "id": "nizhny_novgorod",
        "name": "Нижний Новгород",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 56.3269,
        "longitude": 44.0059,
        "is_active": True
    },
    {
        "id": "samara",
        "name": "Самара",
        "country": "Россия",
        "timezone": "Europe/Samara",
        "currency": "RUB",
        "latitude": 53.1959,
        "longitude": 50.1002,
        "is_active": True
    },
    {
        "id": "ufa",
        "name": "Уфа",
        "country": "Россия",
        "timezone": "Asia/Yekaterinburg",
        "currency": "RUB",
        "latitude": 54.7388,
        "longitude": 55.9721,
        "is_active": True
    },
    {
        "id": "voronezh",
        "name": "Воронеж",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 51.6615,
        "longitude": 39.2003,
        "is_active": True
    },
    {
        "id": "perm",
        "name": "Пермь",
        "country": "Россия",
        "timezone": "Asia/Yekaterinburg",
        "currency": "RUB",
        "latitude": 58.0105,
        "longitude": 56.2502,
        "is_active": True
    },
    {
        "id": "volgograd",
        "name": "Волгоград",
        "country": "Россия",
        "timezone": "Europe/Volgograd",
        "currency": "RUB",
        "latitude": 48.7080,
        "longitude": 44.5133,
        "is_active": True
    },
    {
        "id": "sochi",
        "name": "Сочи",
        "country": "Россия",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "latitude": 43.6028,
        "longitude": 39.7342,
        "is_active": True
    }
]

CATEGORIES_DATA = [
    {"id": "concerts", "name": "Концерты", "slug": "concerts", "is_active": True},
    {"id": "parties", "name": "Вечеринки", "slug": "parties", "is_active": True},
    {"id": "sports", "name": "Спорт", "slug": "sports", "is_active": True},
    {"id": "education", "name": "Образование", "slug": "education", "is_active": True},
    {"id": "business", "name": "Бизнес", "slug": "business", "is_active": True},
    {"id": "exhibitions", "name": "Выставки", "slug": "exhibitions", "is_active": True},
    {"id": "other", "name": "Другое", "slug": "other", "is_active": True},
]


def generate_seed_events(organizer_id: int) -> list:
    now = datetime.now(timezone.utc)

    # 10 Saint Petersburg Events
    spb_events = [
        {
            "id": "spb_01",
            "title": "Tech Meetup SPb: AI & High-Load Systems",
            "description": "Ежемесячный митап инженеров и исследователей. Обсуждаем архитектуру больших языковых моделей и high-load сервисы.",
            "cover_image_url": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800",
            "category_id": "education",
            "city_id": "spb",
            "start_at": now + timedelta(hours=4),  # Today
            "venue_name": "Лофт Проект Этажи",
            "address": "Лиговский пр. 74, Санкт-Петербург",
            "latitude": 59.9221,
            "longitude": 30.3556,
            "price_amount": None,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_02",
            "title": "SPb Indie Rock Live Night",
            "description": "Живой концерт независимых петербургских групп. Уютная клубная атмосфера и аутентичный звук.",
            "cover_image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800",
            "category_id": "concerts",
            "city_id": "spb",
            "start_at": now + timedelta(days=1, hours=2),  # Tomorrow
            "venue_name": "Клуб Космонавт",
            "address": "Бронницкая ул. 24, Санкт-Петербург",
            "latitude": 59.9148,
            "longitude": 30.3182,
            "price_amount": 1200.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_03",
            "title": "Electronic Sunset Rooftop Party",
            "description": "Танцевальная вечеринка на крыше с панорамным видом на Неву и центр Петербурга. Deep house и melodic techno.",
            "cover_image_url": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=800",
            "category_id": "parties",
            "city_id": "spb",
            "start_at": now + timedelta(days=2, hours=5),  # Weekend
            "venue_name": "Крыша Hi-Hat",
            "address": "Аптекарский пр. 4, Санкт-Петербург",
            "latitude": 59.9723,
            "longitude": 30.3155,
            "price_amount": 900.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_04",
            "title": "Neva Morning 10K Running Tour",
            "description": "Совместная утренняя пробежка вдоль набережных Невы. Разминка с профессиональным тренером.",
            "cover_image_url": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800",
            "category_id": "sports",
            "city_id": "spb",
            "start_at": now + timedelta(days=3, hours=1),
            "venue_name": "Дворцовая набережная",
            "address": "Дворцовая наб. 32, Санкт-Петербург",
            "latitude": 59.9419,
            "longitude": 30.3168,
            "price_amount": None,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_05",
            "title": "SPb Founders & IT Breakfast",
            "description": "Встреча основателей технологических стартапов и инвесторов. Питчи проектов и обмен опытом.",
            "cover_image_url": "https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=800",
            "category_id": "business",
            "city_id": "spb",
            "start_at": now + timedelta(days=4, hours=3),
            "venue_name": "Коворкинг Ясная Поляна",
            "address": "ул. Льва Толстого 1-3, Санкт-Петербург",
            "latitude": 59.9658,
            "longitude": 30.3149,
            "price_amount": 1500.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_06",
            "title": "Modern Digital Art Expo",
            "description": "Выставка мультимедийного искусства нового поколения: проекционные инсталляции и generative visual art.",
            "cover_image_url": "https://images.unsplash.com/photo-1508997449629-303059a039c0?w=800",
            "category_id": "exhibitions",
            "city_id": "spb",
            "start_at": now + timedelta(days=5, hours=2),
            "venue_name": "Севкабель Порт",
            "address": "Кожевенная линия 40, Санкт-Петербург",
            "latitude": 59.9242,
            "longitude": 30.2415,
            "price_amount": 600.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_07",
            "title": "SPb Board Games & Social Evening",
            "description": "Уютный вечер настольных игр. Более 100 популярных настолок, ведущие объясняют правила.",
            "cover_image_url": "https://images.unsplash.com/photo-1610890716171-6b1bb98ffd09?w=800",
            "category_id": "other",
            "city_id": "spb",
            "start_at": now + timedelta(days=6, hours=4),
            "venue_name": "Playloft GAGARIN",
            "address": "ул. Марата 34, Санкт-Петербург",
            "latitude": 59.9265,
            "longitude": 30.3498,
            "price_amount": 400.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_08",
            "title": "Jazz Evening: Neva Trio",
            "description": "Классический джаз и современные импровизации в историческом джазовом клубе.",
            "cover_image_url": "https://images.unsplash.com/photo-1511192336575-5a79af67a629?w=800",
            "category_id": "concerts",
            "city_id": "spb",
            "start_at": now + timedelta(days=7, hours=2),
            "venue_name": "JFC Jazz Club",
            "address": "Шпалерная ул. 33, Санкт-Петербург",
            "latitude": 59.9482,
            "longitude": 30.3582,
            "price_amount": 1000.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_09",
            "title": "SPb Squash & Tennis Championship",
            "description": "Любительский турнир по сквошу среди спортсменов уровней B и C. Награды победителям.",
            "cover_image_url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800",
            "category_id": "sports",
            "city_id": "spb",
            "start_at": now + timedelta(days=8, hours=3),
            "venue_name": "RC Club Squash",
            "address": "Крестовский остров, Константиновский пр. 19, Санкт-Петербург",
            "latitude": 59.9729,
            "longitude": 30.2642,
            "price_amount": 1500.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "spb_10",
            "title": "SPb Product Design Workshop",
            "description": "Практический воркшоп по созданию адаптивных мобильных интерфейсов и design systems в Figma.",
            "cover_image_url": "https://images.unsplash.com/photo-1531403009284-440f080d1e12?w=800",
            "category_id": "education",
            "city_id": "spb",
            "start_at": now + timedelta(days=9, hours=4),
            "venue_name": "Пространство К-30",
            "address": "Кожевенная линия 30, Санкт-Петербург",
            "latitude": 59.9231,
            "longitude": 30.2458,
            "price_amount": 2000.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
    ]

    # 10 Makhachkala Events
    makhachkala_events = [
        {
            "id": "mcx_01",
            "title": "Caspian Tech Forum: IT в Дагестане",
            "description": "Главная IT-конференция региона. Доклады от ведущих разработчиков, стартап-питчи и нетворкинг.",
            "cover_image_url": "https://images.unsplash.com/photo-1505373877841-8d25f7d46678?w=800",
            "category_id": "education",
            "city_id": "makhachkala",
            "start_at": now + timedelta(hours=5),  # Today
            "venue_name": "ДГУ Научная Библиотека",
            "address": "ул. Батырая 4, Махачкала",
            "price_amount": None,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_02",
            "title": "Вечер традиционной и современной музыки гор",
            "description": "Аутентичные струнные инструменты, вокал и современная инструментальная обработка народных мотивов.",
            "cover_image_url": "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?w=800",
            "category_id": "concerts",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=1, hours=3),  # Tomorrow
            "venue_name": "Русский драматический театр",
            "address": "ул. Ярагского 75, Махачкала",
            "price_amount": 800.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_03",
            "title": "Открытый турнир по грэпплингу и BJJ",
            "description": "Захватывающие схватки среди лучших борцов Дагестана и СКФО в пяти весовых категориях.",
            "cover_image_url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=800",
            "category_id": "sports",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=2, hours=4),  # Weekend
            "venue_name": "Дворец спорта им. Али Алиева",
            "address": "пр. Насрутдинова 1, Каспийск/Махачкала",
            "price_amount": 500.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_04",
            "title": "Каспийский закат: Акустический джем на набережной",
            "description": "Теплый музыкальный вечер на городском пляже под звуки гитары, саксофона и шум волн.",
            "cover_image_url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800",
            "category_id": "parties",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=3, hours=2),
            "venue_name": "Городской пляж Махачкалы",
            "address": "Родопский бульвар, Махачкала",
            "price_amount": None,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_05",
            "title": "Бизнес-клуб «Вершина»: Инвестиции и франшизы",
            "description": "Встреча предпринимателей республики. Разбор кейсов масштабирования бизнеса и привлечения капитала.",
            "cover_image_url": "https://images.unsplash.com/photo-1528605248644-14dd04022da1?w=800",
            "category_id": "business",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=4, hours=4),
            "venue_name": "Отель «Сарир» Conference Hall",
            "address": "ул. Акушинского 100, Махачкала",
            "price_amount": 1500.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_06",
            "title": "Выставка дагестанского ремесла и серебра Кубачи",
            "description": "Ювелирное искусство, клинковое оружие, керамика Балхар и тканые унцукульские ковры.",
            "cover_image_url": "https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=800",
            "category_id": "exhibitions",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=5, hours=3),
            "venue_name": "Музей изобразительных искусств им. Гамзатовой",
            "address": "ул. Горького 8, Махачкала",
            "price_amount": 300.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_07",
            "title": "Утренний забег на гору Тарки-Тау",
            "description": "Горный трейл-забег с потрясающим панорамным видом на всю Махачкалу и Каспийское море.",
            "cover_image_url": "https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=800",
            "category_id": "sports",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=6, hours=1),
            "venue_name": "Смотровая площадка Тарки-Тау",
            "address": "пос. Тарки, Махачкала",
            "price_amount": None,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_08",
            "title": "Каллиграфия и искусство арабской вязи",
            "description": "Практический мастер-класс от мастера традиционной восточной каллиграфии для начинающих.",
            "cover_image_url": "https://images.unsplash.com/photo-1455390582262-044cdead277a?w=800",
            "category_id": "education",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=7, hours=3),
            "venue_name": "Арт-пространство «Темп»",
            "address": "ул. Буйнакского 4, Махачкала",
            "price_amount": 700.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_09",
            "title": "Гастрономический фестиваль кавказской кухни",
            "description": "Дегустация национальных блюд, мастер-классы от шеф-поваров и гастрономические конкурсы.",
            "cover_image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800",
            "category_id": "other",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=8, hours=5),
            "venue_name": "Парк Ленинского Комсомола",
            "address": "ул. Гаджиева, Махачкала",
            "price_amount": None,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mcx_10",
            "title": "Вечер стендапа: Комики Северного Кавказа",
            "description": "Свежий юмор, честные монологи и живая комедия от резидентов регионального стендап-клуба.",
            "cover_image_url": "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?w=800",
            "category_id": "parties",
            "city_id": "makhachkala",
            "start_at": now + timedelta(days=9, hours=3),
            "venue_name": "Standup Club MCX",
            "address": "ул. Коркмасова 14, Махачкала",
            "price_amount": 600.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
    ]

    # 10 Moscow Events
    moscow_events = [
        {
            "id": "mow_01",
            "title": "Moscow AI Engineers Summit",
            "description": "Крупнейшая встреча специалистов по машинному обучению и LLM. Практика внедрения генеративного ИИ.",
            "cover_image_url": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800",
            "category_id": "education",
            "city_id": "moscow",
            "start_at": now + timedelta(hours=3),  # Today
            "venue_name": "Цифровое Деловое Пространство (ЦДП)",
            "address": "ул. Покровка 47, Москва",
            "price_amount": None,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_02",
            "title": "Симфонический рок: Шедевры Queen и Metallica",
            "description": "Легендарные рок-хиты в исполнении большого симфонического оркестра с мощным световым шоу.",
            "cover_image_url": "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?w=800",
            "category_id": "concerts",
            "city_id": "moscow",
            "start_at": now + timedelta(days=1, hours=4),  # Tomorrow
            "venue_name": "Крокус Сити Холл / МТС Live Холл",
            "address": "ш. Энтузиастов 5, Москва",
            "price_amount": 2500.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_03",
            "title": "Boiler Room Style: Ночь электроники на заводе",
            "description": "Андеграундная вечеринка в лофте бывшего завода. Лайн-ап из ведущих продюсеров модульного звука.",
            "cover_image_url": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=800",
            "category_id": "parties",
            "city_id": "moscow",
            "start_at": now + timedelta(days=2, hours=6),  # Weekend
            "venue_name": "Mutabor / Arma",
            "address": "Шарикоподшипниковская 13, Москва",
            "price_amount": 1200.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_04",
            "title": "Московский полумарафон «Лужники»",
            "description": "Забег по живописным набережным столицы. Дистанции 21.1 км и 10 км. Медаль каждому финишеру.",
            "cover_image_url": "https://images.unsplash.com/photo-1530549387789-4c1017266635?w=800",
            "category_id": "sports",
            "city_id": "moscow",
            "start_at": now + timedelta(days=3, hours=1),
            "venue_name": "Олимпийский комплекс «Лужники»",
            "address": "ул. Лужники 24, Москва",
            "price_amount": 1800.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_05",
            "title": "Moscow Venture Day: Питчи стартапов",
            "description": "Презентации 20 отобранных стартапов ранних стадий перед бизнес-ангелами и инвестиционными синдикатами.",
            "cover_image_url": "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?w=800",
            "category_id": "business",
            "city_id": "moscow",
            "start_at": now + timedelta(days=4, hours=3),
            "venue_name": "Башня «Федерация» Восток, 89 этаж",
            "address": "Пресненская наб. 12, Москва",
            "price_amount": 5000.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_06",
            "title": "Иммерсивная выставка «Вселенная Ван Гога и Климта»",
            "description": "Ожившие полотна великих мастеров в формате 360 градусов с авторским музыкальным сопровождением.",
            "cover_image_url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?w=800",
            "category_id": "exhibitions",
            "city_id": "moscow",
            "start_at": now + timedelta(days=5, hours=2),
            "venue_name": "Artplay Design Center",
            "address": "ул. Нижняя Сыромятническая 10, Москва",
            "price_amount": 900.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_07",
            "title": "Открытый турнир по падел-теннису в Сити",
            "description": "Динамичная игра для любого уровня подготовки. Обучение правилам перед стартом матчей.",
            "cover_image_url": "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=800",
            "category_id": "sports",
            "city_id": "moscow",
            "start_at": now + timedelta(days=6, hours=2),
            "venue_name": "Padel Club Moscow City",
            "address": "Тестовская 1, Москва",
            "price_amount": 1500.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_08",
            "title": "Винный салон и вечер дегустации биодинамики",
            "description": "Лекция от ведущего сомелье, дегустация 7 редких вин Старого и Нового Света с легкими закусками.",
            "cover_image_url": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=800",
            "category_id": "other",
            "city_id": "moscow",
            "start_at": now + timedelta(days=7, hours=4),
            "venue_name": "Винный бар «Сыр и Бокал»",
            "address": "ул. Большая Никитская 22, Москва",
            "price_amount": 3200.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_09",
            "title": "Stand-up Special: Секретный состав",
            "description": "Камерный вечер комедии с популярными участниками ТВ и YouTube проектов. Уютный бар в центре столицы.",
            "cover_image_url": "https://images.unsplash.com/photo-1527529482837-4698179dc6ce?w=800",
            "category_id": "parties",
            "city_id": "moscow",
            "start_at": now + timedelta(days=8, hours=4),
            "venue_name": "StandUp Store Moscow",
            "address": "ул. Петровка 21, Москва",
            "price_amount": 1000.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
        {
            "id": "mow_10",
            "title": "Неоклассика при свечах: Фортепиано и виолончель",
            "description": "Музыка Эйнауди, Циммера и Рихтера в старинном особняке, освещенном тысячью свечей.",
            "cover_image_url": "https://images.unsplash.com/photo-1520523839898-50712140e698?w=800",
            "category_id": "concerts",
            "city_id": "moscow",
            "start_at": now + timedelta(days=9, hours=3),
            "venue_name": "Особняк на Волхонке",
            "address": "Большой Знаменский пер. 2, Москва",
            "price_amount": 2200.0,
            "price_currency": "RUB",
            "status": EventStatus.PUBLISHED.value,
        },
    ]

    return spb_events + makhachkala_events + moscow_events


async def seed_database(session: AsyncSession) -> None:
    """
    Seeds database with initial cities, categories, demo organizer, and realistic events.
    Safe and idempotent: checks existing IDs before inserting and updates attributes.
    """
    # 1. Seed Cities (15 Russian Cities)
    for c_data in CITIES_DATA:
        existing_res = await session.execute(select(City).where(City.id == c_data["id"]))
        existing_city = existing_res.scalar_one_or_none()
        if not existing_city:
            session.add(City(**c_data))
        else:
            existing_city.name = c_data["name"]
            existing_city.country = c_data["country"]
            existing_city.timezone = c_data["timezone"]
            existing_city.currency = c_data["currency"]
            existing_city.latitude = c_data.get("latitude")
            existing_city.longitude = c_data.get("longitude")
            existing_city.is_active = c_data.get("is_active", True)

    # Deactivate Warsaw if present from previous deployment
    waw_res = await session.execute(select(City).where(City.id == "warsaw"))
    waw_city = waw_res.scalar_one_or_none()
    if waw_city:
        waw_city.is_active = False

    await session.commit()

    # 2. Seed Categories
    for cat_data in CATEGORIES_DATA:
        existing = await session.execute(select(Category).where(Category.id == cat_data["id"]))
        if not existing.scalar_one_or_none():
            session.add(Category(**cat_data))
    await session.commit()

    # 3. Seed Demo Organizer / Admin User
    admin_tg_id = 123456789
    user_res = await session.execute(select(User).where(User.telegram_id == admin_tg_id))
    admin_user = user_res.scalar_one_or_none()
    if not admin_user:
        admin_user = User(
            telegram_id=admin_tg_id,
            username="evently_admin",
            first_name="Evently",
            last_name="Curator",
            default_city_id="makhachkala"
        )
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
    else:
        if admin_user.default_city_id == "warsaw":
            admin_user.default_city_id = "makhachkala"
            await session.commit()

    # 4. Seed Events (30 events across SPb, Makhachkala, Moscow)
    events_data = generate_seed_events(organizer_id=admin_user.id)
    for ev_data in events_data:
        existing = await session.execute(select(Event).where(Event.id == ev_data["id"]))
        if not existing.scalar_one_or_none():
            event = Event(organizer_user_id=admin_user.id, **ev_data)
            session.add(event)
    await session.commit()
    logger.info("Database successfully seeded with 15 Russian cities, 7 categories, and 30 demo events.")

