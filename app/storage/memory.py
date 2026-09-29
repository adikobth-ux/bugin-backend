"""Хранилище в памяти: для тестов и запуска без базы. Перезапуск — всё заново."""

import copy
import threading
from datetime import UTC, datetime

from app.storage.base import Record, StoredImage, check_kind


class MemoryStore:
    name = "memory"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[tuple[str, str], Record] = {}
        self._images: dict[str, StoredImage] = {}
        self._flags: dict[str, str] = {}
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def _bump(self) -> None:
        self._revision += 1

    def records(self, kind: str) -> list[Record]:
        check_kind(kind)
        with self._lock:
            return [r for (k, _), r in self._items.items() if k == kind]

    def get(self, kind: str, item_id: str) -> Record | None:
        with self._lock:
            return self._items.get((check_kind(kind), item_id))

    def save(self, kind: str, item_id: str, doc: dict, *, published: bool, demo: bool = False) -> None:
        record = Record(
            kind=check_kind(kind),
            id=item_id,
            doc=copy.deepcopy({**doc, "id": item_id}),
            published=published,
            demo=demo,
            updated_at=datetime.now(UTC),
        )
        with self._lock:
            # Обновление существующего ключа в dict не меняет порядок — как seq в базе.
            self._items[(kind, item_id)] = record
            self._bump()

    def delete(self, kind: str, item_id: str) -> bool:
        with self._lock:
            removed = self._items.pop((check_kind(kind), item_id), None)
            if removed is not None:
                self._bump()
            return removed is not None

    def delete_demo(self) -> int:
        with self._lock:
            demo = [key for key, r in self._items.items() if r.demo]
            for key in demo:
                del self._items[key]
            if demo:
                self._bump()
            return len(demo)

    def save_image(self, image_id: str, content_type: str, data: bytes, width: int, height: int) -> None:
        with self._lock:
            self._images[image_id] = StoredImage(data=data, content_type=content_type)

    def image(self, image_id: str) -> StoredImage | None:
        with self._lock:
            return self._images.get(image_id)

    def delete_images(self, image_ids: list[str]) -> None:
        with self._lock:
            for image_id in image_ids:
                self._images.pop(image_id, None)

    def flag(self, key: str) -> str | None:
        with self._lock:
            return self._flags.get(key)

    def set_flag(self, key: str, value: str) -> None:
        with self._lock:
            self._flags[key] = value
