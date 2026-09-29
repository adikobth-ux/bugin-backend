"""Общие объекты сервера: настройки, хранилище, каталог.

Создаются один раз — при старте (``startup``) или при первом обращении. С
``DATABASE_URL`` хранилище — PostgreSQL, без него — память с тестовыми данными.
Тесты подменяют всё через ``use``.
"""

import logging
import threading

from app import clock, config
from app.domain.catalog import Catalog
from app.storage import demo
from app.storage.base import Store
from app.storage.memory import MemoryStore

log = logging.getLogger(__name__)

_lock = threading.RLock()
_settings: config.Settings | None = None
_store: Store | None = None
_catalog: Catalog | None = None


def settings() -> config.Settings:
    global _settings
    with _lock:
        if _settings is None:
            _settings = config.load()
        return _settings


def _create_store(s: config.Settings) -> Store:
    if s.database_url:
        # psycopg нужен только с базой: без неё сервер и тесты работают и без него.
        from app.storage.postgres import PostgresStore

        store: Store = PostgresStore(s.database_url)
    else:
        log.warning("DATABASE_URL не задан: каталог в памяти, правки пропадут при перезапуске")
        store = MemoryStore()
    if s.seed_demo and demo.seed(store, clock.now()):
        log.info("Заведены тестовые данные прототипа")
    return store


def store() -> Store:
    global _store
    with _lock:
        if _store is None:
            _store = _create_store(settings())
        return _store


def catalog() -> Catalog:
    global _catalog
    with _lock:
        if _catalog is None:
            _catalog = Catalog(store(), public_url=settings().public_url)
        return _catalog


def startup() -> None:
    """Подключиться к базе сразу при старте: ошибка настройки видна в логе деплоя."""
    catalog()


def use(new_store: Store, new_settings: config.Settings | None = None) -> Catalog:
    """Подменить хранилище (и настройки) — для тестов."""
    global _settings, _store, _catalog
    with _lock:
        if new_settings is not None:
            _settings = new_settings
        _store = new_store
        _catalog = Catalog(new_store, public_url=settings().public_url)
        return _catalog


def reset() -> None:
    """Забыть всё созданное: следующее обращение соберёт заново из окружения (для тестов)."""
    global _settings, _store, _catalog
    with _lock:
        _settings, _store, _catalog = None, None, None
