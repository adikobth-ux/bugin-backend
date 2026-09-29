"""Тестовые данные прототипа (8 мест и 8 событий) в хранилище.

Заводятся один раз, в пустую базу, с пометкой «тестовые» — чтобы приложение
не было пустым, пока каталог Астаны наполняется. Удаляются одной кнопкой в админке
и после этого не возвращаются (отметка ``demo_seeded``).
"""

from datetime import datetime

from app.domain import catalog_data
from app.domain.i18n import merge
from app.storage.base import Store

DEMO_FLAG = "demo_seeded"


def documents(now: datetime) -> tuple[list[dict], list[dict]]:
    """Двуязычные документы мест и событий; даты событий — от ``now``.

    Расстояния тестовых мест остаются как в прототипе (в документе есть
    ``distanceKm``), у настоящих мест их считает каталог.
    """
    places = [
        merge(ru, kk)
        for ru, kk in zip(catalog_data.places("ru", now), catalog_data.places("kk", now), strict=True)
    ]
    events = [
        merge(ru, kk)
        for ru, kk in zip(catalog_data.events("ru", now), catalog_data.events("kk", now), strict=True)
    ]
    return places, events


def seed(store: Store, now: datetime) -> bool:
    """Заводит тестовые данные, если их ещё не заводили. True — завели сейчас."""
    if store.flag(DEMO_FLAG) is not None:
        return False
    places, events = documents(now)
    for doc in places:
        store.save("place", doc["id"], doc, published=True, demo=True)
    for doc in events:
        store.save("event", doc["id"], doc, published=True, demo=True)
    store.set_flag(DEMO_FLAG, now.isoformat(timespec="seconds"))
    return True
