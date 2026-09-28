"""Места и события на нужном языке — перенос ``MockPlacesRepository`` и ``MockEventsRepository``.

Данные строит ``catalog_data`` от текущей даты (события «сегодня», «в субботу»),
поэтому снимок кэшируется по паре (язык, дата) и пересобирается с новым днём.
Все функции возвращают dict в формате контракта (``docs/api.md``); вызывающий
код их не меняет — это общие объекты кэша.
"""

import threading
from datetime import date, datetime

from app.domain import catalog_data

EVENT_DAYS = ("today", "tomorrow", "weekend", "date")

_lock = threading.Lock()
_cache: dict[tuple[str, date], tuple[list[dict], list[dict]]] = {}


def _snapshot(lang: str, now: datetime) -> tuple[list[dict], list[dict]]:
    key = (lang, now.date())
    with _lock:
        snapshot = _cache.get(key)
        if snapshot is None:
            # Вчерашние снимки больше не нужны.
            for old in [k for k in _cache if k[1] != key[1]]:
                del _cache[old]
            snapshot = (catalog_data.places(lang, now), catalog_data.events(lang, now))
            _cache[key] = snapshot
        return snapshot


def places(lang: str, now: datetime) -> list[dict]:
    return _snapshot(lang, now)[0]


def events(lang: str, now: datetime) -> list[dict]:
    return _snapshot(lang, now)[1]


def starts_at(event: dict) -> datetime:
    """Начало события как наивный datetime местного времени."""
    return datetime.fromisoformat(event["startsAt"]).replace(tzinfo=None)


def day_diff(a: datetime | date, b: datetime | date) -> int:
    """Разница в календарных днях: a − b (``Fmt.dayDiff``)."""
    a_day = a.date() if isinstance(a, datetime) else a
    b_day = b.date() if isinstance(b, datetime) else b
    return (a_day - b_day).days


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


# ---------- Места ----------


def place(lang: str, now: datetime, place_id: str) -> dict | None:
    return _find(places(lang, now), place_id)


def places_by_ids(lang: str, now: datetime, ids: list[str]) -> list[dict]:
    """Места в порядке ``ids``; неизвестные пропускаются."""
    return _by_ids(places(lang, now), ids)


def nearby(lang: str, now: datetime, limit: int = 6) -> list[dict]:
    """Блок «Сейчас рядом»: порядок ``NEARBY_ORDER``."""
    return places_by_ids(lang, now, list(catalog_data.NEARBY_ORDER))[: max(limit, 0)]


# ---------- События ----------


def event(lang: str, now: datetime, event_id: str) -> dict | None:
    return _find(events(lang, now), event_id)


def events_by_ids(lang: str, now: datetime, ids: list[str]) -> list[dict]:
    """События в порядке ``ids``; неизвестные пропускаются."""
    return _by_ids(events(lang, now), ids)


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


def events_for_day(
    lang: str,
    now: datetime,
    day: str,
    on_date: date | None = None,
    category: str | None = None,
) -> list[dict]:
    """Афиша: события дня (и категории), по времени начала."""
    result = [
        e
        for e in events(lang, now)
        if matches_day(e, day, on_date, now) and (category is None or e["category"] == category)
    ]
    return sorted(result, key=starts_at)


def featured_events(lang: str, now: datetime) -> list[dict]:
    """``isFeatured`` в ближайшие 7 дней, в порядке каталога."""
    return [
        e for e in events(lang, now) if e["isFeatured"] and 0 <= day_diff(starts_at(e), now) < 7
    ]


def similar_events(lang: str, now: datetime, event_id: str, limit: int = 4) -> list[dict]:
    """Сначала той же категории, затем по времени; без самого события."""
    source = event(lang, now, event_id)
    others = [e for e in events(lang, now) if e["id"] != event_id]

    def key(e: dict) -> tuple[int, datetime]:
        same = source is not None and e["category"] == source["category"]
        return (0 if same else 1, starts_at(e))

    return sorted(others, key=key)[: max(limit, 0)]
