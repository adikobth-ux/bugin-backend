"""Каталог: места и события из хранилища на нужном языке, в формате контракта.

Хранилище отдаёт двуязычные документы; каталог выбирает язык, достраивает
вычисляемые поля (расстояние, время на такси, уровень цен, полные ссылки на фото)
и прячет скрытые записи. Снимок кэшируется и перечитывается, когда хранилище
изменилось (``Store.revision``) или прошло ``CACHE_SECONDS``.

Возвращаемые dict — общие объекты кэша: вызывающий код их не меняет.
"""

import threading
import time
from datetime import date, datetime

from app.domain import geo
from app.domain.i18n import localize
from app.storage.base import Store

EVENT_DAYS = ("today", "tomorrow", "weekend", "date")

# Страховка на случай правок в обход этого процесса (второй экземпляр сервера).
CACHE_SECONDS = 600

IMAGE_PATH = "/v1/images/"

# Дальше этого от центра города положение пользователя не учитываем:
# человек в другом городе смотрит Астану — расстояния от центра полезнее.
MAX_ORIGIN_KM = 60

PLACE_DEFAULTS: dict = {
    "subtitle": "",
    "description": "",
    "categoryDetail": "",
    "address": "",
    "phone": "",
    "rating": 0.0,
    "reviewsCount": 0,
    "averageCheck": 0,
    "openingHours": {"opensAt": 0, "closesAt": 1440},
    "photos": [],
    "tags": [],
    "amenities": [],
    "bookingType": "none",
    "bookingUrl": None,
    "pitch": "",
    "goodFor": [],
    "vibes": [],
    "reviews": [],
}

EVENT_DEFAULTS: dict = {
    "subtitle": "",
    "description": "",
    "durationMinutes": 120,
    "venueName": "",
    "address": "",
    "image": "",
    "tags": [],
    "ageLimit": 0,
    "tickets": [],
    "pitch": "",
    "reasons": [],
    "occasions": [],
    "vibes": [],
    "venuePlaceId": None,
    "ticketUrl": None,
    "isFeatured": False,
}


def price_level(average_check: int) -> int:
    """Уровень цен по среднему чеку: ₸ до 3 000, ₸₸ до 7 000, ₸₸₸ до 15 000, дальше ₸₸₸₸."""
    for level, limit in ((1, 3000), (2, 7000), (3, 15000)):
        if average_check <= limit:
            return level
    return 4


def starts_at(event: dict) -> datetime:
    """Начало события как наивный datetime местного времени."""
    return datetime.fromisoformat(event["startsAt"]).replace(tzinfo=None)


def day_diff(a: datetime | date, b: datetime | date) -> int:
    """Разница в календарных днях: a − b (``Fmt.dayDiff``)."""
    a_day = a.date() if isinstance(a, datetime) else a
    b_day = b.date() if isinstance(b, datetime) else b
    return (a_day - b_day).days


def matches_day(item: dict, day: str, on_date: date | None, now: datetime) -> bool:
    """``_matchesDay``: выходные — суббота и воскресенье до ближайшего воскресенья включительно."""
    start = starts_at(item)
    diff = day_diff(start, now)
    to_sunday = (7 - now.isoweekday()) % 7
    is_weekend_day = start.isoweekday() in (6, 7)
    if day == "today":
        return diff == 0
    if day == "tomorrow":
        return diff == 1
    if day == "weekend":
        return 0 <= diff <= to_sunday and is_weekend_day
    if day == "date":
        return on_date is not None and day_diff(start, on_date) == 0
    return False


def _find(items: list[dict], item_id: str) -> dict | None:
    for item in items:
        if item["id"] == item_id:
            return item
    return None


def _by_ids(items: list[dict], ids: list[str]) -> list[dict]:
    result = []
    for item_id in ids:
        item = _find(items, item_id)
        if item is not None:
            result.append(item)
    return result


class Catalog:
    def __init__(
        self,
        store: Store,
        *,
        public_url: str = "",
        origin: tuple[float, float] = geo.ASTANA_CENTER,
    ) -> None:
        self.store = store
        self.public_url = public_url.rstrip("/")
        self.origin = origin
        self._lock = threading.Lock()
        self._raw: tuple[list[dict], list[dict]] = ([], [])
        self._by_lang: dict[str, tuple[list[dict], list[dict]]] = {}
        self._revision = -1
        self._loaded_at = 0.0

    # ---------- Снимок ----------

    def _snapshot(self, lang: str) -> tuple[list[dict], list[dict]]:
        with self._lock:
            revision = self.store.revision
            if revision != self._revision or time.monotonic() - self._loaded_at > CACHE_SECONDS:
                self._raw = (
                    [r.doc for r in self.store.records("place") if r.published],
                    [r.doc for r in self.store.records("event") if r.published],
                )
                self._by_lang = {}
                self._revision = revision
                self._loaded_at = time.monotonic()
            snapshot = self._by_lang.get(lang)
            if snapshot is None:
                places, events = self._raw
                place_ids = {doc.get("id") for doc in places}
                snapshot = (
                    [self._place(doc, lang) for doc in places],
                    [self._event(doc, lang, place_ids) for doc in events],
                )
                self._by_lang[lang] = snapshot
            return snapshot

    def user_origin(self, origin: tuple[float, float] | None) -> tuple[float, float] | None:
        """Точка пользователя, если он в городе; из другого города считаем от центра."""
        if origin is None or geo.distance_km(self.origin, origin) > MAX_ORIGIN_KM:
            return None
        return origin

    def invalidate(self) -> None:
        with self._lock:
            self._revision = -1

    def image_url(self, value: str) -> str:
        """``/v1/images/…`` → полная ссылка; ассеты приложения и чужие ссылки — как есть."""
        if value.startswith(IMAGE_PATH) and self.public_url:
            return self.public_url + value
        return value

    def _location(self, doc: dict) -> tuple[float, float]:
        return geo.point(doc.get("location")) or self.origin

    def _place(self, doc: dict, lang: str) -> dict:
        localized = localize(doc, lang)
        place = {**PLACE_DEFAULTS, **{k: v for k, v in localized.items() if not k.startswith("_")}}
        lat, lng = self._location(doc)
        place["location"] = {"lat": lat, "lng": lng}
        # У тестовых мест расстояние задано в документе, у настоящих — считаем.
        if "distanceKm" not in doc:
            km = geo.distance_km(self.origin, (lat, lng))
            place["distanceKm"] = geo.rounded_km(km)
            place["taxiMinutes"] = geo.taxi_minutes(km)
        place.setdefault("taxiMinutes", geo.taxi_minutes(place["distanceKm"]))
        if "priceLevel" not in doc:
            place["priceLevel"] = price_level(place["averageCheck"])
        place["photos"] = [self.image_url(photo) for photo in place["photos"]]
        return place

    def _event(self, doc: dict, lang: str, place_ids: set) -> dict:
        localized = localize(doc, lang)
        event = {**EVENT_DEFAULTS, **{k: v for k, v in localized.items() if not k.startswith("_")}}
        # Площадку удалили или скрыли — ссылку на неё не отдаём, в приложении была бы пустая страница.
        if event["venuePlaceId"] not in place_ids:
            event["venuePlaceId"] = None
        lat, lng = self._location(doc)
        event["location"] = {"lat": lat, "lng": lng}
        if "distanceKm" not in doc:
            event["distanceKm"] = geo.rounded_km(geo.distance_km(self.origin, (lat, lng)))
        if "priceFrom" not in doc:
            prices = [t["price"] for t in event["tickets"] if isinstance(t.get("price"), int)]
            event["priceFrom"] = min(prices) if prices else 0
        event["image"] = self.image_url(event["image"] or "")
        return event

    # ---------- Места ----------

    # У всех запросов ``origin`` — где пользователь (lat, lng); None — центр города.
    # Расстояния пересчитываются для каждого запроса: снимок кэша общий.

    def places(self, lang: str, origin: tuple[float, float] | None = None) -> list[dict]:
        places = self._snapshot(lang)[0]
        origin = self.user_origin(origin)
        if origin is None:
            return places
        return [self._moved(p, origin, taxi=True) for p in places]

    def place(self, lang: str, place_id: str, origin: tuple[float, float] | None = None) -> dict | None:
        return _find(self.places(lang, origin), place_id)

    def places_by_ids(
        self, lang: str, ids: list[str], origin: tuple[float, float] | None = None
    ) -> list[dict]:
        """Места в порядке ``ids``; неизвестные и скрытые пропускаются."""
        return _by_ids(self.places(lang, origin), ids)

    def nearby(self, lang: str, limit: int = 6, origin: tuple[float, float] | None = None) -> list[dict]:
        """Блок «Сейчас рядом»: ближайшие к ``origin`` (нет — к центру города)."""
        places = self.places(lang, origin)
        return sorted(places, key=lambda p: p["distanceKm"])[: max(limit, 0)]

    @staticmethod
    def _moved(item: dict, origin: tuple[float, float], *, taxi: bool) -> dict:
        km = geo.distance_km(origin, (item["location"]["lat"], item["location"]["lng"]))
        moved = {**item, "distanceKm": geo.rounded_km(km)}
        if taxi:
            moved["taxiMinutes"] = geo.taxi_minutes(km)
        return moved

    # ---------- События ----------

    def events(self, lang: str, origin: tuple[float, float] | None = None) -> list[dict]:
        events = self._snapshot(lang)[1]
        origin = self.user_origin(origin)
        if origin is None:
            return events
        return [self._moved(e, origin, taxi=False) for e in events]

    def event(self, lang: str, event_id: str, origin: tuple[float, float] | None = None) -> dict | None:
        return _find(self.events(lang, origin), event_id)

    def events_by_ids(
        self, lang: str, ids: list[str], origin: tuple[float, float] | None = None
    ) -> list[dict]:
        """События в порядке ``ids``; неизвестные и скрытые пропускаются."""
        return _by_ids(self.events(lang, origin), ids)

    def events_for_day(
        self,
        lang: str,
        now: datetime,
        day: str,
        on_date: date | None = None,
        category: str | None = None,
        origin: tuple[float, float] | None = None,
    ) -> list[dict]:
        """Афиша: события дня (и категории), по времени начала."""
        result = [
            e
            for e in self.events(lang, origin)
            if matches_day(e, day, on_date, now) and (category is None or e["category"] == category)
        ]
        return sorted(result, key=starts_at)

    def featured_events(
        self, lang: str, now: datetime, origin: tuple[float, float] | None = None
    ) -> list[dict]:
        """``isFeatured`` в ближайшие 7 дней, в порядке каталога."""
        return [
            e
            for e in self.events(lang, origin)
            if e["isFeatured"] and 0 <= day_diff(starts_at(e), now) < 7
        ]

    def similar_events(
        self,
        lang: str,
        now: datetime,
        event_id: str,
        limit: int = 4,
        origin: tuple[float, float] | None = None,
    ) -> list[dict]:
        """Сначала той же категории, затем по времени; без самого события и прошедших."""
        source = self.event(lang, event_id)
        others = [
            e
            for e in self.events(lang, origin)
            if e["id"] != event_id and day_diff(starts_at(e), now) >= 0
        ]

        def key(e: dict) -> tuple[int, datetime]:
            same = source is not None and e["category"] == source["category"]
            return (0 if same else 1, starts_at(e))

        return sorted(others, key=key)[: max(limit, 0)]
