"""Хранилище каталога: места, события и фото.

Документ места или события — dict в формате контракта, где тексты могут быть парами
ru/kk (``app.domain.i18n``). Ключи с подчёркиванием (``_mapUrl``) — служебные
для админки, в API не попадают.

Две реализации с одинаковым поведением: ``MemoryStore`` (тесты, запуск без базы)
и ``PostgresStore`` (Neon). Каждое изменение увеличивает ``revision`` — по нему
каталог понимает, что пора перечитать данные.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

KINDS = ("place", "event")


@dataclass(frozen=True)
class Record:
    kind: str
    id: str
    doc: dict
    published: bool
    demo: bool
    updated_at: datetime


@dataclass(frozen=True)
class StoredImage:
    data: bytes
    content_type: str


class Store(Protocol):
    name: str  # «postgres» или «memory»

    @property
    def revision(self) -> int: ...

    def records(self, kind: str) -> list[Record]:
        """Все записи вида в порядке добавления."""
        ...

    def get(self, kind: str, item_id: str) -> Record | None: ...

    def save(self, kind: str, item_id: str, doc: dict, *, published: bool, demo: bool = False) -> None:
        """Создать или заменить запись; порядок добавления у существующей не меняется."""
        ...

    def delete(self, kind: str, item_id: str) -> bool: ...

    def delete_demo(self) -> int:
        """Удалить тестовые записи; возвращает, сколько удалено."""
        ...

    def save_image(self, image_id: str, content_type: str, data: bytes, width: int, height: int) -> None: ...

    def image(self, image_id: str) -> StoredImage | None: ...

    def delete_images(self, image_ids: list[str]) -> None: ...

    def flag(self, key: str) -> str | None:
        """Служебная отметка (например, что тестовые данные уже заводились)."""
        ...

    def set_flag(self, key: str, value: str) -> None: ...


def check_kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"Неизвестный вид записи: {kind}")
    return kind
