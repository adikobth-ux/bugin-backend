"""Тестовые данные прототипа Bugin (этап 0): 8 мест и 8 событий.

Перенесено из Flutter-приложения один в один:
``lib/data/mock_places.dart``, ``lib/data/mock_events.dart``,
``lib/core/app_images.dart``. Каждый элемент — dict с ключами и порядком
``toJson()`` моделей ``Place`` / ``Event`` (см. ``docs/api.md``).

Тексты — парами «русский, казахский» через ``t(ru, kk)``. Даты считаются от
``now`` — наивного datetime местного времени (Asia/Almaty), как в Dart.
"""

from datetime import datetime, timedelta

# --- Места (MockPlaces) -----------------------------------------------------

THE_GARDEN = "the_garden"
COFFEE_LAB = "coffee_lab"
GALAXY_BOWLING = "galaxy_bowling"
SKY_LOUNGE = "sky_lounge"
LUNA_CINEMA = "luna_cinema"
ESIL_EMBANKMENT = "esil_embankment"
HOLST_STUDIO = "holst_studio"
BASTAU_GALLERY = "bastau_gallery"

# Порядок блока «Сейчас рядом» на главной.
NEARBY_ORDER: list[str] = [
    THE_GARDEN,
    COFFEE_LAB,
    GALAXY_BOWLING,
    SKY_LOUNGE,
    LUNA_CINEMA,
    HOLST_STUDIO,
]

# --- События (MockEvents) ---------------------------------------------------

NEON_NIGHTS = "neon_nights"
ROOFTOP_ACOUSTIC = "rooftop_acoustic"
STEPPE_WIND = "steppe_wind"
ART_EVENING = "art_evening"
CITY_OF_LIGHT = "city_of_light"
STANDUP = "standup_evening"
JAZZ = "jazz_on_terrace"
SEAGULL = "seagull_play"

# События вымышленные, поэтому ссылки ведут на разделы афиши операторов.
_TICKETON_ASTANA = "https://ticketon.kz/astana"
_TICKETON_THEATRES = "https://ticketon.kz/astana/theatres"
_KINO_MOVIES = "https://kino.kz/ru/movie"
_KINO_ART = "https://kino.kz/ru/art"
_KINO_STANDUP = "https://kino.kz/ru/standup"

# --- Картинки (AppImages) ---------------------------------------------------

_IMAGES = "assets/images"

_IMG_THE_GARDEN = f"{_IMAGES}/place_the_garden.jpg"
_IMG_THE_GARDEN_HALL = f"{_IMAGES}/place_the_garden_hall.jpg"
_IMG_THE_GARDEN_COFFEE = f"{_IMAGES}/place_the_garden_coffee.jpg"
_IMG_THE_GARDEN_FOOD = f"{_IMAGES}/place_the_garden_food.jpg"
_IMG_THE_GARDEN_NEON = f"{_IMAGES}/place_the_garden_neon.jpg"
_IMG_COFFEE_LAB = f"{_IMAGES}/place_coffee_lab.jpg"
_IMG_GALAXY_BOWLING = f"{_IMAGES}/place_galaxy_bowling.jpg"
_IMG_SKY_LOUNGE = f"{_IMAGES}/place_sky_lounge.jpg"
_IMG_LUNA_CINEMA = f"{_IMAGES}/place_luna_cinema.jpg"
_IMG_HOLST_STUDIO = f"{_IMAGES}/place_holst_studio.jpg"
_IMG_BASTAU_GALLERY = f"{_IMAGES}/place_bastau_gallery.jpg"

_IMG_NEON_NIGHTS = f"{_IMAGES}/event_neon_nights.jpg"
_IMG_ROOFTOP_ACOUSTIC = f"{_IMAGES}/event_rooftop_acoustic.jpg"


# --- Сборка JSON в порядке toJson() -----------------------------------------


def _iso(moment: datetime) -> str:
    """Местное время без смещения и без долей секунды: 2026-10-03T20:00:00."""
    return moment.isoformat(timespec="seconds")


def _translator(lang: str):
    """Как в Dart: ``t(ru, kk)`` отдаёт казахский только для ``kk``."""
    is_kk = lang == "kk"

    def t(ru: str, kk: str) -> str:
        return kk if is_kk else ru

    return t


def _hours(opens_at: int, closes_at: int) -> dict:
    return {"opensAt": opens_at, "closesAt": closes_at}


# OpeningHours.always()
_ALWAYS = (0, 1440)


def _geo(lat: float, lng: float) -> dict:
    return {"lat": float(lat), "lng": float(lng)}


def _amenity(type_: str, value: str) -> dict:
    return {"type": type_, "value": value}


def _review(author: str, rating: float, text: str, date: datetime) -> dict:
    return {"author": author, "rating": float(rating), "text": text, "date": _iso(date)}


def _ticket(name: str, price: int) -> dict:
    return {"name": name, "price": price}


def _place(
    *,
    id: str,
    name: str,
    subtitle: str,
    description: str,
    category: str,
    categoryDetail: str,
    address: str,
    phone: str,
    rating: float,
    reviewsCount: int,
    priceLevel: int,
    averageCheck: int,
    openingHours: tuple[int, int],
    photos: list[str],
    tags: list[str],
    amenities: list[dict],
    distanceKm: float,
    taxiMinutes: int,
    bookingType: str,
    pitch: str,
    goodFor: list[str],
    vibes: list[str],
    location: tuple[float, float],
    reviews: list[dict] | None = None,
    bookingUrl: str | None = None,
) -> dict:
    return {
        "id": id,
        "name": name,
        "subtitle": subtitle,
        "description": description,
        "category": category,
        "categoryDetail": categoryDetail,
        "address": address,
        "phone": phone,
        "rating": float(rating),
        "reviewsCount": reviewsCount,
        "priceLevel": priceLevel,
        "averageCheck": averageCheck,
        "openingHours": _hours(*openingHours),
        "photos": list(photos),
        "tags": list(tags),
        "amenities": list(amenities),
        "distanceKm": float(distanceKm),
        "taxiMinutes": taxiMinutes,
        "bookingType": bookingType,
        "pitch": pitch,
        "goodFor": list(goodFor),
        "vibes": list(vibes),
        "location": _geo(*location),
        "reviews": list(reviews or []),
        "bookingUrl": bookingUrl,
    }


def _event(
    *,
    id: str,
    title: str,
    subtitle: str,
    description: str,
    category: str,
    startsAt: datetime,
    durationMinutes: int,
    venueName: str,
    address: str,
    location: tuple[float, float],
    distanceKm: float,
    priceFrom: int,
    image: str,
    tags: list[str],
    ageLimit: int,
    tickets: list[dict],
    pitch: str,
    reasons: list[str],
    occasions: list[str],
    vibes: list[str],
    venuePlaceId: str | None = None,
    ticketUrl: str | None = None,
    isFeatured: bool = False,
) -> dict:
    return {
        "id": id,
        "title": title,
        "subtitle": subtitle,
        "description": description,
        "category": category,
        "startsAt": _iso(startsAt),
        "durationMinutes": durationMinutes,
        "venueName": venueName,
        "address": address,
        "location": _geo(*location),
        "distanceKm": float(distanceKm),
        "priceFrom": priceFrom,
        "image": image,
        "tags": list(tags),
        "ageLimit": ageLimit,
        "tickets": list(tickets),
        "pitch": pitch,
        "reasons": list(reasons),
        "occasions": list(occasions),
        "vibes": list(vibes),
        "venuePlaceId": venuePlaceId,
        "ticketUrl": ticketUrl,
        "isFeatured": isFeatured,
    }


# --- Каталог мест -----------------------------------------------------------


def places(lang: str, now: datetime) -> list[dict]:
    """Все места каталога (MockPlaces.build) на языке ``lang``."""
    t = _translator(lang)

    def days_ago(days: int) -> datetime:
        return now - timedelta(days=days)

    return [
        _place(
            id=THE_GARDEN,
            name="The Garden",
            subtitle=t(
                "Европейская кухня и завтраки весь день",
                "Еуропа асханасы және күні бойы таңғы ас",
            ),
            description=t(
                "Уютное кафе в центре города: живая зелень, тёплый свет и европейская "
                "кухня. Днём здесь завтракают и работают, вечером ужинают вдвоём под "
                "тихую музыку. По пятницам — живые акустические сеты.",
                "Қала орталығындағы жайлы кафе: жасыл өсімдіктер, жылы жарық және "
                "еуропа асханасы. Күндіз мұнда таңғы ас ішіп, жұмыс істейді, кешке "
                "тыныш әуен астында екеулеп кешкі ас ішеді. Жұма сайын — жанды "
                "акустикалық сеттер.",
            ),
            category="cafe",
            categoryDetail=t("европейская кухня", "еуропа асханасы"),
            address=t("ул. Абая, 57", "Абай көшесі, 57"),
            phone="+7 700 123 45 67",
            rating=4.8,
            reviewsCount=1540,
            priceLevel=2,
            averageCheck=6000,
            openingHours=(8 * 60, 23 * 60),
            photos=[
                _IMG_THE_GARDEN,
                _IMG_THE_GARDEN_HALL,
                _IMG_THE_GARDEN_COFFEE,
                _IMG_THE_GARDEN_FOOD,
                _IMG_THE_GARDEN_NEON,
            ],
            tags=[
                t("Европейская кухня", "Еуропа асханасы"),
                t("Завтраки", "Таңғы ас"),
                t("Кофе", "Кофе"),
                t("Уютная атмосфера", "Жайлы атмосфера"),
            ],
            amenities=[
                _amenity("wifi", t("Бесплатный", "Тегін")),
                _amenity("pets", t("Можно", "Болады")),
                _amenity("smoking", t("Нельзя", "Болмайды")),
                _amenity("payment", t("Карта, наличные", "Карта, қолма-қол")),
            ],
            distanceKm=1.5,
            taxiMinutes=6,
            bookingType="table",
            pitch=t(
                "Уютно, живая зелень и тихая музыка",
                "Жайлы, жасыл өсімдіктер мен тыныш музыка",
            ),
            goodFor=["date", "friends", "solo", "work"],
            vibes=["beautiful", "calm"],
            location=(51.1283, 71.4305),
            reviews=[
                _review(
                    "Алина",
                    5,
                    t(
                        "Очень уютно вечером, по пятницам живая музыка. Десерты — отдельная "
                        "любовь, особенно чизкейк.",
                        "Кешке өте жайлы, жұма сайын жанды музыка. Десерттері — бөлек "
                        "әңгіме, әсіресе чизкейк.",
                    ),
                    days_ago(2),
                ),
                _review(
                    "Тимур",
                    4.5,
                    t(
                        "Хорошее место для завтрака и спокойной встречи. В выходные лучше "
                        "бронировать стол заранее.",
                        "Таңғы асқа және тыныш кездесуге жақсы орын. Демалыс күндері "
                        "үстелді алдын ала брондаған дұрыс.",
                    ),
                    days_ago(9),
                ),
                _review(
                    "Дана",
                    5,
                    t(
                        "Красиво, тихо и вкусно. Брали пасту и лимонад — всё понравилось.",
                        "Әдемі, тыныш әрі дәмді. Паста мен лимонад алдық — бәрі ұнады.",
                    ),
                    days_ago(21),
                ),
            ],
        ),
        _place(
            id=COFFEE_LAB,
            name="Coffee Lab",
            subtitle=t(
                "Спешелти-кофе и домашние десерты",
                "Спешелти-кофе және үй десерттері",
            ),
            description=t(
                "Кофейня с собственной обжаркой. Большие столы, розетки у каждого места "
                "и тихая музыка — удобно поработать или встретиться за десертом.",
                "Кофені өздері қуыратын кофехана. Үлкен үстелдер, әр орында розетка "
                "және тыныш музыка — жұмыс істеуге немесе десерт үстінде "
                "кездесуге ыңғайлы.",
            ),
            category="coffeeShop",
            categoryDetail=t("десерты", "десерттер"),
            address=t("пр. Мангилик Ел, 20", "Мәңгілік Ел даңғылы, 20"),
            phone="+7 701 555 20 20",
            rating=4.7,
            reviewsCount=892,
            priceLevel=2,
            averageCheck=4500,
            openingHours=(7 * 60 + 30, 22 * 60),
            photos=[_IMG_COFFEE_LAB],
            tags=[
                t("Кофе", "Кофе"),
                t("Десерты", "Десерттер"),
                t("Для работы", "Жұмыс үшін"),
            ],
            amenities=[
                _amenity("wifi", t("Бесплатный", "Тегін")),
                _amenity("sockets", t("У каждого стола", "Әр үстелде")),
                _amenity("smoking", t("Нельзя", "Болмайды")),
                _amenity("payment", t("Карта, QR", "Карта, QR")),
            ],
            distanceKm=1.1,
            taxiMinutes=5,
            bookingType="none",
            pitch=t("Тихо и уютно", "Тыныш әрі жайлы"),
            goodFor=["date", "work", "solo", "friends"],
            vibes=["calm"],
            location=(51.1302, 71.4247),
            reviews=[
                _review(
                    "Ерлан",
                    5,
                    t(
                        "Лучший флэт уайт в районе, и никто не торопит, если сидишь с ноутбуком.",
                        "Аудандағы ең жақсы флэт уайт, ноутбукпен отырсаң да ешкім "
                        "асықтырмайды.",
                    ),
                    days_ago(4),
                ),
            ],
        ),
        _place(
            id=GALAXY_BOWLING,
            name="Galaxy Bowling",
            subtitle=t("Боулинг, бильярд и кухня", "Боулинг, бильярд және тағамдар"),
            description=t(
                "12 дорожек с неоновой подсветкой, бильярд и кухня. Хорошо на компанию: "
                "дорожку можно забронировать заранее и не ждать.",
                "Неон жарығы бар 12 жолақ, бильярд және тағамдар. Топпен келуге "
                "жақсы: жолақты алдын ала брондап, кезек күтпеуге болады.",
            ),
            category="bowling",
            categoryDetail=t("12 дорожек", "12 жолақ"),
            address=t("ул. Кунаева, 12", "Қонаев көшесі, 12"),
            phone="+7 702 300 12 12",
            rating=4.7,
            reviewsCount=2310,
            priceLevel=2,
            averageCheck=4000,
            openingHours=(12 * 60, 26 * 60),
            photos=[_IMG_GALAXY_BOWLING],
            tags=[
                t("Боулинг", "Боулинг"),
                t("Друзья", "Достар"),
                t("Музыка", "Музыка"),
            ],
            amenities=[
                _amenity("parking", t("Бесплатная", "Тегін")),
                _amenity("payment", t("Карта, наличные", "Карта, қолма-қол")),
                _amenity("smoking", t("Нельзя", "Болмайды")),
                _amenity("wifi", t("Бесплатный", "Тегін")),
            ],
            distanceKm=1.2,
            taxiMinutes=5,
            bookingType="lane",
            pitch=t("Весело и динамично", "Көңілді әрі серпінді"),
            goodFor=["friends", "family", "date"],
            vibes=["active"],
            location=(51.1265, 71.4371),
            reviews=[
                _review(
                    "Марат",
                    4.5,
                    t(
                        "Отмечали день рождения — дорожки новые, музыка громкая, кухня норм.",
                        "Туған күнді атап өттік — жолақтары жаңа, музыкасы қатты, тамағы "
                        "да жаман емес.",
                    ),
                    days_ago(6),
                ),
            ],
        ),
        _place(
            id=SKY_LOUNGE,
            name="Sky Lounge",
            subtitle=t(
                "Ресторан с панорамным видом на город",
                "Қаланың панорамалық көрінісі бар мейрамхана",
            ),
            description=t(
                "Ресторан на 24 этаже с панорамными окнами. Лучшие места — у окна на "
                "закате, их стоит бронировать заранее.",
                "24-қабаттағы панорамалық терезелері бар мейрамхана. Ең жақсы "
                "орындар — күн батарда терезе жанында, оларды алдын ала брондаған "
                "жөн.",
            ),
            category="restaurant",
            categoryDetail=t("24 этаж", "24-қабат"),
            address=t("пр. Туран, 37", "Тұран даңғылы, 37"),
            phone="+7 705 240 24 24",
            rating=4.6,
            reviewsCount=1210,
            priceLevel=3,
            averageCheck=8000,
            openingHours=(12 * 60, 24 * 60),
            photos=[_IMG_SKY_LOUNGE],
            tags=[
                t("Панорамный вид", "Панорамалық көрініс"),
                t("Коктейли", "Коктейльдер"),
                t("Ужин", "Кешкі ас"),
            ],
            amenities=[
                _amenity("wifi", t("Бесплатный", "Тегін")),
                _amenity("smoking", t("На террасе", "Террасада")),
                _amenity("payment", t("Карта", "Карта")),
                _amenity("parking", t("Подземная", "Жерасты")),
            ],
            distanceKm=1.8,
            taxiMinutes=8,
            bookingType="table",
            pitch=t(
                "Панорамный вид на город — красиво вечером",
                "Қаланың панорамалық көрінісі — кешке әдемі",
            ),
            goodFor=["date", "friends"],
            vibes=["beautiful"],
            location=(51.1244, 71.4198),
            reviews=[
                _review(
                    t("Айгерим", "Айгерім"),
                    5,
                    t(
                        "Вид потрясающий, особенно на закате. Цены выше среднего, но оно того стоит.",
                        "Көрінісі керемет, әсіресе күн батқанда. Бағасы орташадан жоғары, "
                        "бірақ соған тұрарлық.",
                    ),
                    days_ago(3),
                ),
            ],
        ),
        _place(
            id=LUNA_CINEMA,
            name="Luna Cinema",
            subtitle=t("Кинотеатр с залом IMAX", "IMAX залы бар кинотеатр"),
            description=t(
                "Современный кинотеатр с удобными креслами и залом IMAX. Вечерние сеансы "
                "начинаются в 20:00 и 21:30.",
                "Жайлы орындықтары мен IMAX залы бар заманауи кинотеатр. Кешкі "
                "сеанстар 20:00 мен 21:30-да басталады.",
            ),
            category="cinema",
            categoryDetail=t("8 залов", "8 зал"),
            address=t("ул. Сыганак, 10", "Сығанақ көшесі, 10"),
            phone="+7 707 111 70 70",
            rating=4.5,
            reviewsCount=2280,
            priceLevel=2,
            averageCheck=5000,
            openingHours=(10 * 60, 26 * 60),
            photos=[_IMG_LUNA_CINEMA],
            tags=[
                t("Кино", "Кино"),
                t("Премьеры", "Премьералар"),
                "IMAX",
            ],
            amenities=[
                _amenity("parking", t("Бесплатная", "Тегін")),
                _amenity("payment", t("Карта, наличные", "Карта, қолма-қол")),
            ],
            distanceKm=1.9,
            taxiMinutes=8,
            bookingType="ticket",
            bookingUrl="https://kino.kz/ru/movie",
            pitch=t(
                "Вечерние сеансы в 20:00 и 21:30",
                "Кешкі сеанстар 20:00 мен 21:30-да",
            ),
            goodFor=["date", "friends", "family"],
            vibes=["calm"],
            location=(51.1219, 71.4282),
            reviews=[
                _review(
                    t("Нурлан", "Нұрлан"),
                    4.5,
                    t(
                        "Зал IMAX отличный, кресла удобные. Попкорн дорогой, как везде.",
                        "IMAX залы керемет, орындықтары жайлы. Попкорны қымбат, басқа "
                        "жерлердегідей.",
                    ),
                    days_ago(12),
                ),
            ],
        ),
        _place(
            id=ESIL_EMBANKMENT,
            name=t("Набережная Есиля", "Есіл жағалауы"),
            subtitle=t("Прогулочная зона вдоль реки", "Өзен бойындағы серуен аймағы"),
            description=t(
                "Прогулочная зона вдоль реки: вечерняя подсветка, скамейки и виды на "
                "город. Удобно пройтись между ужином и кино.",
                "Өзен бойындағы серуен аймағы: кешкі жарықтандыру, орындықтар және "
                "қала көріністері. Кешкі ас пен кино арасында серуендеуге ыңғайлы.",
            ),
            category="park",
            categoryDetail=t("прогулка", "серуен"),
            address=t("Набережная Есиля", "Есіл жағалауы"),
            phone="",
            rating=4.9,
            reviewsCount=3120,
            priceLevel=1,
            averageCheck=0,
            openingHours=_ALWAYS,
            photos=[],
            tags=[
                t("Прогулка", "Серуен"),
                t("Виды", "Көріністер"),
                t("Бесплатно", "Тегін"),
            ],
            amenities=[],
            distanceKm=0.9,
            taxiMinutes=4,
            bookingType="none",
            pitch=t(
                "Красивые виды и огни вечером",
                "Әдемі көріністер мен кешкі шамдар",
            ),
            goodFor=["date", "friends", "family", "solo"],
            vibes=["beautiful", "calm"],
            location=(51.1331, 71.4201),
        ),
        _place(
            id=HOLST_STUDIO,
            name=t("Студия «Холст»", "«Холст» студиясы"),
            subtitle=t(
                "Мастер-классы по живописи для новичков",
                "Бастаушыларға кескіндемеден шеберлік сабақтары",
            ),
            description=t(
                "Творческая студия, где проводят мастер-классы по живописи для новичков. "
                "Все материалы включены, картину забираете с собой.",
                "Бастаушыларға кескіндемеден шеберлік сабақтарын өткізетін "
                "шығармашылық студия. Барлық материалдар бағаға қосылған, салған "
                "суретті өздеріңмен алып кетесіңдер.",
            ),
            category="studio",
            categoryDetail=t("мастер-классы", "шеберлік сабақтары"),
            address=t("ул. Кенесары, 40", "Кенесары көшесі, 40"),
            phone="+7 708 456 78 90",
            rating=4.9,
            reviewsCount=346,
            priceLevel=2,
            averageCheck=7000,
            openingHours=(11 * 60, 22 * 60),
            photos=[_IMG_HOLST_STUDIO],
            tags=[
                t("Для двоих", "Екі адамға"),
                t("Все материалы", "Барлық материалдар"),
                t("Опыт не нужен", "Тәжірибе керек емес"),
            ],
            amenities=[
                _amenity("payment", t("Карта, наличные", "Карта, қолма-қол")),
                _amenity("wifi", t("Бесплатный", "Тегін")),
            ],
            distanceKm=2.1,
            taxiMinutes=9,
            bookingType="ticket",
            bookingUrl="https://ticketon.kz/astana",
            pitch=t(
                "Необычный вариант для двоих — опыт не нужен",
                "Екі адамға ерекше нұсқа — тәжірибе керек емес",
            ),
            goodFor=["date", "friends", "solo"],
            vibes=["novelty", "calm"],
            location=(51.1357, 71.4412),
        ),
        _place(
            id=BASTAU_GALLERY,
            name=t("Галерея «Бастау»", "«Бастау» галереясы"),
            subtitle=t(
                "Современное искусство и фотография",
                "Заманауи өнер және фотография",
            ),
            description=t(
                "Небольшая галерея современного искусства и фотографии. Выставки "
                "меняются раз в месяц, по четвергам — бесплатные экскурсии.",
                "Заманауи өнер мен фотографияның шағын галереясы. Көрмелер айына бір "
                "рет ауысады, бейсенбі сайын — тегін экскурсиялар.",
            ),
            category="gallery",
            categoryDetail=t("современное искусство", "заманауи өнер"),
            address=t("ул. Бейбитшилик, 18", "Бейбітшілік көшесі, 18"),
            phone="+7 747 310 31 31",
            rating=4.6,
            reviewsCount=518,
            priceLevel=1,
            averageCheck=3000,
            openingHours=(10 * 60, 22 * 60),
            photos=[_IMG_BASTAU_GALLERY],
            tags=[
                t("Выставки", "Көрмелер"),
                t("Фотография", "Фотография"),
            ],
            amenities=[
                _amenity("payment", t("Карта", "Карта")),
            ],
            distanceKm=3.0,
            taxiMinutes=11,
            bookingType="ticket",
            bookingUrl="https://kino.kz/ru/art",
            pitch=t(
                "Тихо, красиво и есть о чём поговорить",
                "Тыныш, әдемі және сөйлесетін тақырып көп",
            ),
            goodFor=["date", "solo", "friends"],
            vibes=["calm", "beautiful"],
            location=(51.1391, 71.4108),
        ),
    ]


# --- Афиша ------------------------------------------------------------------


def events(lang: str, now: datetime) -> list[dict]:
    """Все события афиши (MockEvents.build) на языке ``lang``.

    Даты считаются от ``now``, поэтому афиша всегда «свежая».
    """
    t = _translator(lang)
    midnight = datetime(now.year, now.month, now.day)

    def at(day_offset: int, hour: int, minute: int) -> datetime:
        return midnight + timedelta(days=day_offset, hours=hour, minutes=minute)

    # Ближайшая суббота (сегодня, если сегодня суббота) и ближайшее воскресенье
    # (сегодня, если сегодня воскресенье). weekday(): понедельник = 0.
    to_saturday = (5 - now.weekday()) % 7
    to_sunday = (6 - now.weekday()) % 7

    return [
        _event(
            id=NEON_NIGHTS,
            title="Neon Nights",
            subtitle=t(
                "Живой концерт электро-поп группы",
                "Электро-поп тобының жанды концерті",
            ),
            description=t(
                "Neon Nights впервые выступают в Астане с новой программой: синтезаторы, "
                "живые барабаны и световое шоу. Два с половиной часа музыки без перерыва.",
                "Neon Nights Астанада алғаш рет жаңа бағдарламамен өнер көрсетеді: "
                "синтезаторлар, жанды барабандар және жарық шоуы. Екі жарым сағат "
                "үзіліссіз музыка.",
            ),
            category="concert",
            startsAt=at(to_saturday, 20, 0),
            durationMinutes=150,
            venueName="Sky Arena",
            address=t("пр. Туран, 50", "Тұран даңғылы, 50"),
            location=(51.1102, 71.4029),
            distanceKm=4.2,
            priceFrom=12000,
            image=_IMG_NEON_NIGHTS,
            tags=[
                t("Электро-поп", "Электро-поп"),
                t("Живой звук", "Жанды дыбыс"),
                t("Танцпол", "Би алаңы"),
            ],
            ageLimit=16,
            tickets=[
                _ticket(t("Танцпартер", "Би партері"), 12000),
                _ticket(t("Трибуна", "Трибуна"), 15000),
                _ticket("VIP", 30000),
            ],
            pitch=t("Живой звук и световое шоу", "Жанды дыбыс және жарық шоуы"),
            reasons=[
                t("Концерты — в твоих интересах", "Концерттер — сенің қызығушылықтарыңның бірі"),
                t("Живой звук и световое шоу", "Жанды дыбыс және жарық шоуы"),
                t("Хорошо для вечера с друзьями", "Достармен кеш өткізуге жақсы"),
            ],
            ticketUrl=_TICKETON_ASTANA,
            occasions=["friends", "date"],
            vibes=["active"],
            isFeatured=True,
        ),
        _event(
            id=ROOFTOP_ACOUSTIC,
            title=t("Акустика на крыше", "Шатырдағы акустика"),
            subtitle=t(
                "Живая музыка под открытым небом",
                "Ашық аспан астындағы жанды музыка",
            ),
            description=t(
                "Камерный акустический концерт на крыше лофта: гитара, голос и виды на "
                "вечерний город. Пледы и горячий чай — на месте.",
                "Лофт шатырындағы камералық акустикалық концерт: гитара, дауыс және "
                "кешкі қала көріністері. Плед пен ыстық шай — сол жерде.",
            ),
            category="concert",
            startsAt=at(0, 20, 0),
            durationMinutes=120,
            venueName=t("Лофт «Кенес»", "«Кеңес» лофты"),
            address=t("ул. Сарайшык, 5", "Сарайшық көшесі, 5"),
            location=(51.1297, 71.4156),
            distanceKm=2.4,
            priceFrom=5000,
            image=_IMG_ROOFTOP_ACOUSTIC,
            tags=[
                t("Акустика", "Акустика"),
                t("Под открытым небом", "Ашық аспан астында"),
            ],
            ageLimit=12,
            tickets=[_ticket(t("Входной билет", "Кіру билеті"), 5000)],
            pitch=t(
                "Камерно и красиво — вид на вечерний город",
                "Оңаша әрі әдемі — кешкі қала көрінісі",
            ),
            reasons=[
                t("Камерная атмосфера без толпы", "Көп адамсыз оңаша атмосфера"),
                t(
                    "Билет от 5 000 ₸ — в твоём бюджете",
                    "Билет 5 000 ₸-ден бастап — бюджетіңе сай",
                ),
                t("Красивый вид на вечерний город", "Кешкі қаланың әдемі көрінісі"),
            ],
            ticketUrl=_TICKETON_ASTANA,
            occasions=["date", "friends", "solo"],
            vibes=["beautiful", "calm"],
        ),
        _event(
            id=STEPPE_WIND,
            title=t("Премьера «Степной ветер»", "«Дала желі» премьерасы"),
            subtitle=t(
                "Драма о большой дороге домой",
                "Үйге апаратын ұзақ жол туралы драма",
            ),
            description=t(
                "Новый фильм о путешествии через степь и возвращении домой. Показ в зале "
                "IMAX, после сеанса — короткая встреча с режиссёром.",
                "Дала арқылы саяхат пен үйге оралу туралы жаңа фильм. Көрсетілім IMAX "
                "залында, сеанстан кейін — режиссермен қысқа кездесу.",
            ),
            category="cinema",
            startsAt=at(0, 21, 30),
            durationMinutes=125,
            venueName="Luna Cinema",
            address=t("ул. Сыганак, 10", "Сығанақ көшесі, 10"),
            location=(51.1219, 71.4282),
            distanceKm=1.9,
            priceFrom=2500,
            image=_IMG_LUNA_CINEMA,
            tags=[
                t("Драма", "Драма"),
                t("Премьера", "Премьера"),
                "IMAX",
            ],
            ageLimit=16,
            tickets=[
                _ticket(t("Стандарт", "Стандарт"), 2500),
                _ticket(t("Комфорт", "Комфорт"), 3500),
            ],
            pitch=t(
                "Премьера в IMAX и встреча с режиссёром",
                "IMAX-тағы премьера және режиссермен кездесу",
            ),
            reasons=[
                t(
                    "Премьера — первые показы в городе",
                    "Премьера — қаладағы алғашқы көрсетілімдер",
                ),
                t("Кино вдвоём — классика вечера", "Екеулеп кино көру — кештің классикасы"),
                t("Билет от 2 500 ₸", "Билет 2 500 ₸-ден бастап"),
            ],
            ticketUrl=_KINO_MOVIES,
            occasions=["date", "friends", "solo"],
            vibes=["calm"],
            venuePlaceId=LUNA_CINEMA,
        ),
        _event(
            id=ART_EVENING,
            title=t("Арт-вечер: живопись", "Арт-кеш: кескіндеме"),
            subtitle=t("Мастер-класс для новичков", "Бастаушыларға шеберлік сабағы"),
            description=t(
                "Пишем картину маслом под руководством художника. Все материалы включены, "
                "опыт не нужен — результат забираете с собой.",
                "Суретшінің жетекшілігімен майлы бояумен сурет саламыз. Барлық "
                "материалдар бағаға қосылған, тәжірибе керек емес — дайын суретті "
                "өздеріңмен алып кетесіңдер.",
            ),
            category="workshop",
            startsAt=at(0, 19, 0),
            durationMinutes=120,
            venueName=t("Студия «Холст»", "«Холст» студиясы"),
            address=t("ул. Кенесары, 40", "Кенесары көшесі, 40"),
            location=(51.1357, 71.4412),
            distanceKm=2.1,
            priceFrom=7000,
            image=_IMG_HOLST_STUDIO,
            tags=[
                t("Для двоих", "Екі адамға"),
                t("Все материалы", "Барлық материалдар"),
                t("Опыт не нужен", "Тәжірибе керек емес"),
            ],
            ageLimit=14,
            tickets=[_ticket(t("Участие", "Қатысу"), 7000)],
            pitch=t(
                "Необычный вариант для двоих — опыт не нужен",
                "Екі адамға ерекше нұсқа — тәжірибе керек емес",
            ),
            reasons=[
                t("Необычный формат для свидания", "Кездесуге арналған ерекше формат"),
                t("Все материалы уже включены", "Барлық материалдар бағаға қосылған"),
                t("Картину заберёте с собой", "Суретті өздеріңмен алып кетесіңдер"),
            ],
            ticketUrl=_TICKETON_ASTANA,
            occasions=["date", "friends", "solo"],
            vibes=["novelty", "calm"],
            venuePlaceId=HOLST_STUDIO,
        ),
        _event(
            id=CITY_OF_LIGHT,
            title=t("Выставка «Город света»", "«Жарық қаласы» көрмесі"),
            subtitle=t(
                "Ночная фотография мегаполисов",
                "Мегаполистердің түнгі фотосуреттері",
            ),
            description=t(
                "Фотографии ночных городов мира: неон, отражения и длинная выдержка. "
                "По вечерам работает аудиогид.",
                "Әлемнің түнгі қалаларының фотосуреттері: неон, шағылысулар және ұзақ "
                "экспозиция. Кешке аудиогид жұмыс істейді.",
            ),
            category="exhibition",
            startsAt=at(0, 10, 0),
            durationMinutes=720,
            venueName=t("Галерея «Бастау»", "«Бастау» галереясы"),
            address=t("ул. Бейбитшилик, 18", "Бейбітшілік көшесі, 18"),
            location=(51.1391, 71.4108),
            distanceKm=3.0,
            priceFrom=3000,
            image=_IMG_BASTAU_GALLERY,
            tags=[
                t("Фотография", "Фотография"),
                t("Современное искусство", "Заманауи өнер"),
            ],
            ageLimit=0,
            tickets=[_ticket(t("Входной билет", "Кіру билеті"), 3000)],
            pitch=t(
                "Тихо, красиво и есть о чём поговорить",
                "Тыныш, әдемі және сөйлесетін тақырып көп",
            ),
            reasons=[
                t("Спокойный формат без спешки", "Асығыссыз, тыныш формат"),
                t(
                    "Можно прийти в любое время до 22:00",
                    "22:00-ге дейін кез келген уақытта келуге болады",
                ),
                t("Билет 3 000 ₸", "Билет 3 000 ₸"),
            ],
            ticketUrl=_KINO_ART,
            occasions=["date", "solo", "friends"],
            vibes=["calm", "beautiful"],
            venuePlaceId=BASTAU_GALLERY,
        ),
        _event(
            id=JAZZ,
            title=t("Джаз на веранде", "Верандадағы джаз"),
            subtitle=t("Трио живого джаза", "Жанды джаз триосы"),
            description=t(
                "Живой джаз на веранде The Garden: трио, лёгкие стандарты и авторские "
                "композиции. Столы у сцены лучше бронировать.",
                "The Garden верандасында жанды джаз: трио, жеңіл стандарттар және "
                "авторлық композициялар. Сахна жанындағы үстелдерді брондаған дұрыс.",
            ),
            category="concert",
            startsAt=at(1, 19, 30),
            durationMinutes=120,
            venueName="The Garden",
            address=t("ул. Абая, 57", "Абай көшесі, 57"),
            location=(51.1283, 71.4305),
            distanceKm=1.5,
            priceFrom=3000,
            image=_IMG_THE_GARDEN_HALL,
            tags=[
                t("Джаз", "Джаз"),
                t("Живой звук", "Жанды дыбыс"),
            ],
            ageLimit=0,
            tickets=[_ticket(t("Вход", "Кіру"), 3000)],
            pitch=t(
                "Живой джаз и ужин в одном месте",
                "Жанды джаз бен кешкі ас бір жерде",
            ),
            reasons=[
                t("Ужин и музыка без переездов", "Кешкі ас пен музыка бір жерде"),
                t("Вход 3 000 ₸", "Кіру 3 000 ₸"),
                t("Спокойная атмосфера", "Тыныш атмосфера"),
            ],
            ticketUrl=_TICKETON_ASTANA,
            occasions=["date", "friends"],
            vibes=["calm", "beautiful"],
            venuePlaceId=THE_GARDEN,
        ),
        _event(
            id=STANDUP,
            title=t("Стендап «Свои люди»", "«Өзіміздікілер» стендапы"),
            subtitle=t("Вечер открытого микрофона", "Ашық микрофон кеші"),
            description=t(
                "Молодые комики пробуют новый материал. Формат открытого микрофона: "
                "восемь выступлений по десять минут.",
                "Жас комиктер жаңа материалын сынап көреді. Ашық микрофон форматы: "
                "әрқайсысы он минуттық сегіз нөмір.",
            ),
            category="standup",
            startsAt=at(1, 20, 0),
            durationMinutes=100,
            venueName=t("Бар «Сцена»", "«Сцена» бары"),
            address=t("ул. Достык, 9", "Достық көшесі, 9"),
            location=(51.1271, 71.4459),
            distanceKm=2.8,
            priceFrom=4000,
            image="",
            tags=[
                t("Юмор", "Әзіл"),
                t("Открытый микрофон", "Ашық микрофон"),
            ],
            ageLimit=18,
            tickets=[_ticket(t("Вход", "Кіру"), 4000)],
            pitch=t("Посмеяться компанией", "Достармен бірге күліп алу"),
            reasons=[
                t("Весёлый вечер с друзьями", "Достармен көңілді кеш"),
                t("Билет 4 000 ₸", "Билет 4 000 ₸"),
            ],
            ticketUrl=_KINO_STANDUP,
            occasions=["friends"],
            vibes=["active", "novelty"],
        ),
        _event(
            id=SEAGULL,
            title=t("Спектакль «Чайка»", "«Шағала» спектаклі"),
            subtitle=t("Классика в камерном зале", "Камералық залдағы классика"),
            description=t(
                "Пьеса Чехова в современной постановке камерного театра. Зал на 80 мест, "
                "зрители сидят совсем близко к сцене.",
                "Чеховтың пьесасы камералық театрдың заманауи қойылымында. 80 орындық "
                "зал, көрермендер сахнаға өте жақын отырады.",
            ),
            category="theatre",
            startsAt=at(to_sunday, 18, 0),
            durationMinutes=150,
            venueName=t("Камерный театр «Арка»", "«Арқа» камералық театры"),
            address=t("ул. Иманова, 11", "Иманов көшесі, 11"),
            location=(51.1702, 71.4203),
            distanceKm=3.4,
            priceFrom=6000,
            image="",
            tags=[
                t("Классика", "Классика"),
                t("Камерный зал", "Камералық зал"),
            ],
            ageLimit=12,
            tickets=[
                _ticket(t("Партер", "Партер"), 6000),
                _ticket(t("Первые ряды", "Алдыңғы қатарлар"), 9000),
            ],
            pitch=t("Классика совсем близко к сцене", "Сахнаның дәл жанында классика"),
            reasons=[
                t("Камерный зал на 80 мест", "80 орындық камералық зал"),
                t("Классика в современной постановке", "Заманауи қойылымдағы классика"),
            ],
            ticketUrl=_TICKETON_THEATRES,
            occasions=["date", "solo", "family"],
            vibes=["calm", "beautiful"],
        ),
    ]
