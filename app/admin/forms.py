"""Поля форм админки: как документ места или события превращается в форму и обратно.

Каждое поле описано один раз (``Field``): шаблон рисует его по виду (``kind``),
``fill`` раскладывает документ в строки формы, ``parse`` собирает документ из
отправленной формы и возвращает ошибки по полям. Фото загружаются отдельно
(``app.admin.photos``) — сюда приходят уже готовые ссылки.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.domain import geo, i18n

PLACE_CATEGORIES = [
    ("cafe", "Кафе"),
    ("coffeeShop", "Кофейня"),
    ("restaurant", "Ресторан"),
    ("bowling", "Боулинг"),
    ("cinema", "Кинотеатр"),
    ("park", "Парк, набережная"),
    ("gallery", "Галерея, музей"),
    ("studio", "Мастерская, студия"),
]
EVENT_CATEGORIES = [
    ("concert", "Концерт"),
    ("cinema", "Кино"),
    ("theatre", "Театр"),
    ("exhibition", "Выставка"),
    ("workshop", "Мастер-класс"),
    ("standup", "Стендап"),
]
BOOKING_TYPES = [
    ("none", "Без брони — просто прийти"),
    ("table", "Столик"),
    ("ticket", "Билеты"),
    ("lane", "Дорожка (боулинг)"),
]
OCCASIONS = [
    ("date", "Свидание"),
    ("friends", "С друзьями"),
    ("work", "Поработать"),
    ("family", "С семьёй"),
    ("solo", "Для себя"),
]
VIBES = [
    ("beautiful", "Красиво"),
    ("calm", "Спокойно"),
    ("active", "Активно"),
    ("novelty", "Что-то новое"),
]
AMENITIES = [
    ("wifi", "Wi-Fi", "Бесплатный"),
    ("sockets", "Розетки", "У каждого стола"),
    ("payment", "Оплата", "Карта, наличные"),
    ("parking", "Парковка", "Бесплатная"),
    ("pets", "С животными", "Можно"),
    ("smoking", "Курение", "Нельзя"),
]
AGE_LIMITS = [("0", "0+"), ("6", "6+"), ("12", "12+"), ("16", "16+"), ("18", "18+")]


class FormLike(Protocol):
    """``starlette.datastructures.FormData`` и всё, что умеет так же."""

    def get(self, key: str, default: Any = None) -> Any: ...

    def getlist(self, key: str) -> list[Any]: ...


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str
    section: str
    required: bool = False
    help: str = ""
    placeholder: str = ""
    options: list[tuple[str, str]] = field(default_factory=list)
    minimum: int | None = None
    maximum: int | None = None
    default: Any = None


@dataclass
class Parsed:
    """Итог разбора формы: документ, ошибки по полям и фото, которые больше не нужны."""

    doc: dict
    errors: dict[str, str]
    removed_images: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class Context:
    """Что нужно разбору кроме самой формы."""

    previous: dict = field(default_factory=dict)  # документ до правки ({} — новый)
    uploads: dict[str, list[str]] = field(default_factory=dict)  # поле → ссылки на новые фото
    resolved_geo: tuple[float, float] | None = None  # координаты из короткой ссылки
    places: dict[str, dict] = field(default_factory=dict)  # id → документ места (для событий)


# ---------- Описание форм ----------

PLACE_FIELDS: list[Field] = [
    Field("name", "Название", "text_i18n", "Главное", required=True, placeholder="The Garden"),
    Field("category", "Категория", "select", "Главное", required=True, options=PLACE_CATEGORIES),
    Field(
        "categoryDetail", "Уточнение", "text_i18n", "Главное",
        placeholder="европейская кухня", help="Мелко под названием: кухня, жанр, формат.",
    ),
    Field(
        "subtitle", "Коротко", "text_i18n", "Главное",
        placeholder="Европейская кухня и завтраки весь день", help="Одна строка в карточке.",
    ),
    Field(
        "pitch", "Почему сюда", "text_i18n", "Главное",
        placeholder="Уютно, живая зелень и тихая музыка",
        help="Одной фразой — её показывает AI-поиск в объяснении.",
    ),
    Field("description", "Описание", "area_i18n", "Главное"),
    Field("address", "Адрес", "text_i18n", "Где", required=True, placeholder="ул. Абая, 57"),
    Field(
        "location", "Место на карте", "geo", "Где", required=True,
        help="Откройте место в 2ГИС, Google Maps или Яндекс Картах → «Поделиться» → "
        "скопируйте ссылку и вставьте сюда. Координаты возьмём из неё.",
    ),
    Field("phone", "Телефон", "text", "Где", placeholder="+7 700 123 45 67"),
    Field(
        "averageCheck", "Средний чек на человека, ₸", "int", "Цены и бронь",
        required=True, minimum=0, maximum=1_000_000, placeholder="6000", help="0 — бесплатно.",
    ),
    Field("openingHours", "Часы работы", "hours", "Цены и бронь", required=True),
    Field("bookingType", "Бронь", "select", "Цены и бронь", required=True, options=BOOKING_TYPES, default="none"),
    Field(
        "bookingUrl", "Ссылка на бронь или билеты", "url", "Цены и бронь",
        placeholder="https://kino.kz/…",
        help="Кнопка в приложении откроет её. Для кино — страница на Kino.kz или Ticketon.",
    ),
    Field("goodFor", "Кому подходит", "multi", "Для кого", options=OCCASIONS),
    Field("vibes", "Настроение", "multi", "Для кого", options=VIBES),
    Field(
        "tags", "Теги", "list_i18n", "Для кого",
        placeholder="Завтраки, Кофе, Терраса", help="Через запятую.",
    ),
    Field(
        "amenities", "Удобства", "amenities", "Удобства",
        help="Заполните только то, что есть; пустые строки в приложении не показываются.",
    ),
    Field(
        "photos", "Фото", "photos", "Фото",
        help="Первое — главное. Можно выбрать несколько сразу; большие фото уменьшим сами.",
    ),
    Field("rating", "Рейтинг", "float", "Рейтинг", minimum=0, maximum=5, default=0.0, placeholder="4.8"),
    Field("reviewsCount", "Число отзывов", "int", "Рейтинг", minimum=0, maximum=10_000_000, default=0),
]

EVENT_FIELDS: list[Field] = [
    Field("title", "Название", "text_i18n", "Главное", required=True, placeholder="Neon Nights"),
    Field("category", "Категория", "select", "Главное", required=True, options=EVENT_CATEGORIES),
    Field("subtitle", "Коротко", "text_i18n", "Главное", help="Одна строка в карточке."),
    Field(
        "pitch", "Почему стоит пойти", "text_i18n", "Главное",
        help="Одной фразой — её показывает AI-поиск в объяснении.",
    ),
    Field("description", "Описание", "area_i18n", "Главное"),
    Field("startsAt", "Начало", "datetime", "Когда", required=True, help="Время Астаны."),
    Field(
        "durationMinutes", "Длительность, минут", "int", "Когда",
        required=True, minimum=10, maximum=60 * 24 * 60, default=120,
        help="Выставка на месяц — 43200 минут: тогда событие видно весь день.",
    ),
    Field(
        "venuePlaceId", "Площадка из каталога", "place_ref", "Где",
        help="Если площадка есть среди мест — выберите, адрес и карту возьмём оттуда.",
    ),
    Field("venueName", "Площадка", "text_i18n", "Где", placeholder="Барыс Арена"),
    Field("address", "Адрес", "text_i18n", "Где"),
    Field(
        "location", "Место на карте", "geo", "Где",
        help="Ссылка из 2ГИС, Google Maps или Яндекс Карт. Не нужна, если выбрана площадка.",
    ),
    Field(
        "tickets", "Категории билетов", "tickets", "Билеты",
        help="По строке на категорию: «Танцпартер — 12000». На казахском — только названия, "
        "в том же порядке.",
    ),
    Field(
        "priceFrom", "Цена от, ₸", "int", "Билеты", minimum=0, maximum=10_000_000, default=0,
        help="Если категорий нет. С категориями считается сама — по самой дешёвой.",
    ),
    Field(
        "ticketUrl", "Ссылка на билеты", "url", "Билеты",
        placeholder="https://ticketon.kz/…", help="Ticketon, Kino.kz или сайт организатора.",
    ),
    Field("ageLimit", "Возраст", "select", "Билеты", options=AGE_LIMITS, default="0"),
    Field("occasions", "Кому подходит", "multi", "Для кого", options=OCCASIONS),
    Field("vibes", "Настроение", "multi", "Для кого", options=VIBES),
    Field("tags", "Теги", "list_i18n", "Для кого", placeholder="Электроника, Танцы", help="Через запятую."),
    Field(
        "reasons", "Почему понравится", "lines_i18n", "Для кого",
        help="По строке на причину — показываются на странице события.",
    ),
    Field("image", "Картинка", "image", "Картинка"),
    Field(
        "isFeatured", "Главное событие недели", "bool", "Показ",
        help="Попадёт в подборку на главной, если до него меньше недели.",
    ),
]


def sections(fields: list[Field]) -> list[tuple[str, list[Field]]]:
    result: list[tuple[str, list[Field]]] = []
    for f in fields:
        if not result or result[-1][0] != f.section:
            result.append((f.section, []))
        result[-1][1].append(f)
    return result


# ---------- Документ → строки формы ----------


def _pair_values(value: object) -> tuple[Any, Any]:
    if i18n.is_pair(value):
        return value.get("ru", ""), value.get("kk", "")
    return value, ""


def _minutes_text(minutes: int) -> str:
    minutes %= 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def fill(fields: list[Field], doc: dict) -> dict[str, Any]:
    """Значения полей формы для документа (новый — пустой ``{}``)."""
    values: dict[str, Any] = {}
    for f in fields:
        value = doc.get(f.key, f.default)
        k = f.key
        if f.kind in ("text_i18n", "area_i18n"):
            ru, kk = _pair_values(value)
            values[f"{k}.ru"], values[f"{k}.kk"] = ru or "", kk or ""
        elif f.kind in ("list_i18n", "lines_i18n"):
            ru, kk = _pair_values(value or [])
            sep = ", " if f.kind == "list_i18n" else "\n"
            values[f"{k}.ru"] = sep.join(ru or [])
            values[f"{k}.kk"] = sep.join(kk or [])
        elif f.kind in ("text", "url", "select", "place_ref"):
            values[k] = "" if value is None else str(value)
        elif f.kind in ("int", "float"):
            # Новой записи подсказываем только осмысленные умолчания (120 минут), не нули.
            hide = value is None or (not doc and not f.default)
            values[k] = "" if hide else str(value)
        elif f.kind == "multi":
            values[k] = list(value or [])
        elif f.kind == "bool":
            values[k] = bool(value)
        elif f.kind == "hours":
            hours = value or {}
            opens, closes = hours.get("opensAt"), hours.get("closesAt")
            always = opens == 0 and isinstance(closes, int) and closes >= 1440
            values[f"{k}.always"] = always
            values[f"{k}.opens"] = "" if opens is None or always else _minutes_text(opens)
            values[f"{k}.closes"] = "" if closes is None or always else _minutes_text(closes)
        elif f.kind == "datetime":
            values[k] = (value or "")[:16]
        elif f.kind == "geo":
            point = geo.point(value)
            values["_mapUrl"] = doc.get("_mapUrl", "")
            values[f"{k}.lat"] = "" if point is None else f"{point[0]:.6f}"
            values[f"{k}.lng"] = "" if point is None else f"{point[1]:.6f}"
        elif f.kind == "amenities":
            by_type = {a.get("type"): a.get("value") for a in value or []}
            for code, _, _ in AMENITIES:
                ru, kk = _pair_values(by_type.get(code, ""))
                values[f"{k}.{code}.ru"], values[f"{k}.{code}.kk"] = ru or "", kk or ""
        elif f.kind == "tickets":
            ru_lines, kk_lines = [], []
            for ticket in value or []:
                ru, kk = _pair_values(ticket.get("name", ""))
                ru_lines.append(f"{ru} — {ticket.get('price', 0)}")
                # Строки по-казахски идут в том же порядке: вместо пустой — русское название,
                # иначе названия съедут на соседние категории.
                kk_lines.append(kk or ru)
            values[f"{k}.ru"] = "\n".join(ru_lines)
            values[f"{k}.kk"] = "\n".join(kk_lines) if any(_pair_values(t.get("name", ""))[1] for t in value or []) else ""
        elif f.kind == "photos":
            values[k] = list(value or [])
        elif f.kind == "image":
            values[k] = value or ""
    return values


# ---------- Строки формы → документ ----------

_SPACES = re.compile(r"[\s ]+")
_TIME = re.compile(r"^(\d{1,2})[:.](\d{2})$")
_DATETIME = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::\d{2})?$")
_TICKET = re.compile(r"^(.*?)[\s ]*[—–\-:][\s ]*(\d[\d\s ]*)\s*₸?\s*$")
_LINE_PRICE = re.compile(r"^(\d[\d\s ]*)\s*₸?\s*$")


def _text(form: FormLike, name: str) -> str:
    value = form.get(name)
    return value.replace("\r\n", "\n").strip() if isinstance(value, str) else ""


def _split(text: str, sep: str) -> list[str]:
    parts = text.split("\n") if sep == "\n" else text.split(",")
    return [part.strip() for part in parts if part.strip()]


def _int(text: str) -> int | None:
    digits = _SPACES.sub("", text)
    return int(digits) if digits.isdigit() else None


def _minutes(text: str) -> int | None:
    m = _TIME.match(text)
    if not m:
        return None
    hours, minutes = int(m.group(1)), int(m.group(2))
    if hours > 24 or minutes > 59 or (hours == 24 and minutes):
        return None
    return hours * 60 + minutes


def _is_url(text: str) -> bool:
    return text.startswith(("https://", "http://")) and " " not in text and len(text) <= 2000


def parse(fields: list[Field], form: FormLike, ctx: Context) -> Parsed:
    """Собирает документ из формы поверх ``ctx.previous`` (незнакомые форме ключи сохраняются)."""
    doc = {k: v for k, v in ctx.previous.items()}
    errors: dict[str, str] = {}
    removed: list[str] = []

    for f in fields:
        k = f.key
        if f.kind in ("text_i18n", "area_i18n"):
            ru, kk = _text(form, f"{k}.ru"), _text(form, f"{k}.kk")
            if f.required and not ru:
                errors[k] = "Заполните по-русски"
            doc[k] = i18n.pair(ru, kk)
        elif f.kind in ("list_i18n", "lines_i18n"):
            sep = "," if f.kind == "list_i18n" else "\n"
            doc[k] = i18n.pair(_split(_text(form, f"{k}.ru"), sep), _split(_text(form, f"{k}.kk"), sep))
        elif f.kind == "text":
            doc[k] = _text(form, k)
        elif f.kind == "url":
            url = _text(form, k)
            if url and not _is_url(url):
                errors[k] = "Ссылка должна начинаться с https://"
            doc[k] = url or None
        elif f.kind == "int":
            raw = _text(form, k)
            number = _int(raw) if raw else f.default
            if raw and number is None:
                errors[k] = "Нужно целое число"
            elif number is None and f.required:
                errors[k] = "Заполните"
            elif number is not None and (
                (f.minimum is not None and number < f.minimum)
                or (f.maximum is not None and number > f.maximum)
            ):
                errors[k] = f"От {f.minimum} до {f.maximum}"
            doc[k] = number if number is not None else f.default
        elif f.kind == "float":
            raw = _text(form, k).replace(",", ".")
            try:
                number = float(raw) if raw else f.default
            except ValueError:
                number = None
                errors[k] = "Нужно число, например 4.8"
            if number is not None and f.minimum is not None and f.maximum is not None:
                if not f.minimum <= number <= f.maximum:
                    errors[k] = f"От {f.minimum} до {f.maximum}"
            doc[k] = float(number) if number is not None else f.default
        elif f.kind == "select":
            value = _text(form, k) or (f.default or "")
            codes = [code for code, _ in f.options]
            if value not in codes:
                if f.required or value:
                    errors[k] = "Выберите из списка"
                value = f.default
            doc[k] = int(value) if k == "ageLimit" and value is not None else value
        elif f.kind == "multi":
            codes = [code for code, _ in f.options]
            chosen = set(form.getlist(k))
            doc[k] = [code for code in codes if code in chosen]
        elif f.kind == "bool":
            doc[k] = form.get(k) in ("on", "1", "true")
        elif f.kind == "hours":
            if form.get(f"{k}.always") in ("on", "1", "true"):
                doc[k] = {"opensAt": 0, "closesAt": 1440}
            else:
                opens, closes = _minutes(_text(form, f"{k}.opens")), _minutes(_text(form, f"{k}.closes"))
                if opens is None or closes is None:
                    errors[k] = "Укажите время, например 08:00 и 23:00, или «Круглосуточно»"
                    doc[k] = ctx.previous.get(k, {"opensAt": 0, "closesAt": 1440})
                else:
                    opens %= 1440
                    if closes <= opens:
                        closes += 1440  # закрывается после полуночи
                    doc[k] = {"opensAt": opens, "closesAt": closes}
        elif f.kind == "datetime":
            m = _DATETIME.match(_text(form, k))
            if m:
                doc[k] = f"{m.group(1)}T{m.group(2)}:00"
            elif f.required:
                errors[k] = "Укажите дату и время"
        elif f.kind == "place_ref":
            value = _text(form, k)
            doc[k] = value if value in ctx.places else None
        elif f.kind == "geo":
            _parse_geo(f, form, ctx, doc, errors)
        elif f.kind == "amenities":
            amenities = []
            for code, _, _ in AMENITIES:
                ru, kk = _text(form, f"{k}.{code}.ru"), _text(form, f"{k}.{code}.kk")
                if ru:
                    amenities.append({"type": code, "value": i18n.pair(ru, kk)})
            doc[k] = amenities
        elif f.kind == "tickets":
            _parse_tickets(f, form, doc, errors)
        elif f.kind == "photos":
            before = list(ctx.previous.get(k) or [])
            keep = [url for url in form.getlist(f"{k}.keep") if url in before]
            drop = set(form.getlist(f"{k}.remove"))
            photos = [url for url in keep if url not in drop]
            cover = form.get(f"{k}.cover")
            if cover in photos:
                photos.remove(cover)
                photos.insert(0, cover)
            photos += ctx.uploads.get(k, [])
            removed += [url for url in before if url not in photos]
            doc[k] = photos
        elif f.kind == "image":
            before = ctx.previous.get(k) or ""
            new = ctx.uploads.get(k, [])
            if new:
                value = new[0]
            elif form.get(f"{k}.remove") in ("on", "1", "true"):
                value = ""
            else:
                value = before
            if before and before != value:
                removed.append(before)
            doc[k] = value

    _derive(doc, ctx)
    return Parsed(doc=doc, errors=errors, removed_images=removed)


def _coords(lat_text: str, lng_text: str) -> tuple[float, float] | None:
    try:
        lat, lng = float(lat_text.replace(",", ".")), float(lng_text.replace(",", "."))
    except ValueError:
        return None
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


def _parse_geo(f: Field, form: FormLike, ctx: Context, doc: dict, errors: dict[str, str]) -> None:
    """Координаты: новая ссылка на карту → поля «широта/долгота» → площадка события."""
    k = f.key
    link = _text(form, "_mapUrl")
    lat_text, lng_text = _text(form, f"{k}.lat"), _text(form, f"{k}.lng")
    doc["_mapUrl"] = link
    point: tuple[float, float] | None = None

    if link and link != ctx.previous.get("_mapUrl", ""):
        point = ctx.resolved_geo or geo.parse_map_link(link)
        if point is None:
            errors[k] = (
                "Не нашёл координаты в ссылке. Вставьте ссылку из 2ГИС или Google Maps "
                "или сотрите её и впишите координаты вручную."
            )
            return

    venue_id = doc.get("venuePlaceId")
    venue = ctx.places.get(venue_id or "")
    venue_changed = venue is not None and venue_id != ctx.previous.get("venuePlaceId")
    if point is None and venue_changed:
        point = geo.point(venue.get("location"))

    if point is None and (lat_text or lng_text):
        point = _coords(lat_text, lng_text)
        if point is None:
            errors[k] = "Координаты — два числа, например 51.128 и 71.430"
            return

    if point is None and venue is not None:
        point = geo.point(venue.get("location"))

    if point is None:
        doc.pop(k, None)
        if f.required:
            errors[k] = "Вставьте ссылку на место в 2ГИС или Google Maps"
        return
    doc[k] = {"lat": round(point[0], 6), "lng": round(point[1], 6)}


def _parse_tickets(f: Field, form: FormLike, doc: dict, errors: dict[str, str]) -> None:
    # Казахское название — из строки с тем же номером; пустые строки номера не сдвигают.
    ru_lines = [line.strip() for line in _text(form, f"{f.key}.ru").split("\n")]
    kk_lines = [line.strip() for line in _text(form, f"{f.key}.kk").split("\n")]
    tickets = []
    for i, line in enumerate(ru_lines):
        if not line:
            continue
        m = _TICKET.match(line)
        if m and m.group(1):
            name, price = m.group(1).strip(), _int(m.group(2))
        elif _LINE_PRICE.match(line):
            name, price = "Билет", _int(_LINE_PRICE.match(line).group(1))
        else:
            errors[f.key] = f"В строке «{line}» нет цены. Пример: «Танцпартер — 12000»"
            continue
        kk = kk_lines[i] if i < len(kk_lines) else ""
        tickets.append({"name": i18n.pair(name, kk), "price": price or 0})
    doc[f.key] = tickets


def _derive(doc: dict, ctx: Context) -> None:
    """Поля, которые считаются из других: цена «от», площадка события."""
    if "tickets" in doc and doc["tickets"]:
        doc["priceFrom"] = min(t["price"] for t in doc["tickets"])
    venue = ctx.places.get(doc.get("venuePlaceId") or "")
    if venue is not None:
        if not i18n.text(doc.get("venueName")):
            doc["venueName"] = venue.get("name", "")
        if not i18n.text(doc.get("address")):
            doc["address"] = venue.get("address", "")
    # Расстояния и уровень цен настоящих записей считает каталог.
    for key in ("distanceKm", "taxiMinutes", "priceLevel"):
        doc.pop(key, None)


# ---------- id новых записей ----------

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ә": "a", "ғ": "g", "қ": "q", "ң": "n", "ө": "o", "ұ": "u", "ү": "u",
    "һ": "h", "і": "i",
}


def slug(text: str) -> str:
    """«Кофейня Март» → «kofeynya-mart». Латиница и цифры, до 40 символов."""
    latin = "".join(_TRANSLIT.get(ch, ch) for ch in text.lower())
    cleaned = re.sub(r"[^a-z0-9]+", "-", latin).strip("-")
    return cleaned[:40].strip("-")


def new_id(name: str, exists: Callable[[str], bool], fallback: str) -> str:
    """Постоянный id: из названия, при совпадении — с номером."""
    base = slug(name) or fallback
    candidate, n = base, 2
    while exists(candidate):
        candidate = f"{base}-{n}"
        n += 1
    return candidate
