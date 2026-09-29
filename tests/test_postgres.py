"""Хранилище в PostgreSQL ведёт себя так же, как в памяти.

Нужна база: ``TEST_DATABASE_URL=postgresql://…`` (в CI — сервис postgres). Без неё
тесты пропускаются, а в CI — падают, чтобы проверка базы не выпала незаметно.
Таблицы очищаются перед каждым тестом — не указывайте рабочую базу.
"""

import os
import unittest
from datetime import datetime

URL = os.environ.get("TEST_DATABASE_URL", "")
if not URL:
    if os.environ.get("CI"):
        raise RuntimeError("В CI нужен TEST_DATABASE_URL")
    raise unittest.SkipTest("нет TEST_DATABASE_URL")

from app.domain.catalog import Catalog  # noqa: E402
from app.storage import demo  # noqa: E402
from app.storage.memory import MemoryStore  # noqa: E402
from app.storage.postgres import MIGRATIONS, PostgresStore  # noqa: E402

NOW = datetime(2026, 9, 29, 12, 0)


class PostgresStoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PostgresStore(URL, max_size=2)

    @classmethod
    def tearDownClass(cls):
        cls.store.close()

    def setUp(self):
        with self.store._pool.connection() as conn:
            conn.execute("truncate catalog_items, images, flags restart identity")

    def test_migrations_are_idempotent(self):
        self.assertEqual(self.store.migrate(), len(MIGRATIONS))
        self.assertEqual(self.store.migrate(), len(MIGRATIONS))
        self.assertTrue(self.store.ping())

    def test_save_get_order_and_revision(self):
        revision = self.store.revision
        self.store.save("place", "b", {"name": {"ru": "Б", "kk": "Б-kk"}, "n": 1}, published=True)
        self.store.save("place", "a", {"name": "А"}, published=False, demo=True)
        self.store.save("place", "b", {"name": "Б2"}, published=True)  # правка не меняет порядок
        self.assertGreater(self.store.revision, revision)

        records = self.store.records("place")
        self.assertEqual([r.id for r in records], ["b", "a"])
        self.assertEqual(records[0].doc, {"id": "b", "name": "Б2"})
        self.assertFalse(records[1].published)
        self.assertTrue(records[1].demo)
        self.assertIsNotNone(records[0].updated_at.tzinfo)
        self.assertEqual(self.store.get("place", "a").doc["name"], "А")
        self.assertIsNone(self.store.get("event", "a"))
        self.assertEqual(self.store.records("event"), [])

    def test_delete_and_demo(self):
        self.store.save("event", "x", {"title": "X"}, published=True)
        self.store.save("event", "d", {"title": "D"}, published=True, demo=True)
        self.assertTrue(self.store.delete("event", "x"))
        self.assertFalse(self.store.delete("event", "x"))
        self.assertEqual(self.store.delete_demo(), 1)
        self.assertEqual(self.store.records("event"), [])

    def test_images_and_flags(self):
        self.store.save_image("ab12", "image/jpeg", b"\xff\xd8jpeg", 10, 20)
        stored = self.store.image("ab12")
        self.assertEqual((stored.data, stored.content_type), (b"\xff\xd8jpeg", "image/jpeg"))
        self.store.delete_images(["ab12", "nope"])
        self.assertIsNone(self.store.image("ab12"))
        self.assertIsNone(self.store.flag("k"))
        self.store.set_flag("k", "1")
        self.store.set_flag("k", "2")
        self.assertEqual(self.store.flag("k"), "2")

    def test_catalog_is_the_same_as_in_memory(self):
        memory = MemoryStore()
        self.assertTrue(demo.seed(memory, NOW))
        self.assertTrue(demo.seed(self.store, NOW))
        self.assertFalse(demo.seed(self.store, NOW))
        for lang in ("ru", "kk"):
            self.assertEqual(Catalog(self.store).places(lang), Catalog(memory).places(lang))
            self.assertEqual(Catalog(self.store).events(lang), Catalog(memory).events(lang))


if __name__ == "__main__":
    unittest.main()
