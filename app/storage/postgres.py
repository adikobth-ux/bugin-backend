"""Хранилище в PostgreSQL (Neon, позже — облако в Казахстане).

Одна таблица на места и события (``catalog_items``, документ — jsonb), фото — в
``images`` (bytea: на этапе 1 это сотни снимков, отдельное файловое хранилище пока
не нужно). Схема обновляется при старте: номера применённых миграций лежат
в ``schema_version``, параллельные старты разводит advisory-блокировка.
"""

import threading

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from app.storage.base import Record, StoredImage, check_kind

# Каждая миграция — список отдельных SQL-команд. Уже выпущенные не меняются: новые
# изменения схемы — новым элементом в конце.
MIGRATIONS: list[list[str]] = [
    [
        """
        create table catalog_items (
            kind text not null check (kind in ('place', 'event')),
            id text not null,
            doc jsonb not null,
            published boolean not null default true,
            demo boolean not null default false,
            seq bigserial not null,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            primary key (kind, id)
        )
        """,
        """
        create table images (
            id text primary key,
            content_type text not null,
            data bytea not null,
            width integer not null,
            height integer not null,
            created_at timestamptz not null default now()
        )
        """,
        """
        create table flags (
            key text primary key,
            value text not null
        )
        """,
    ],
]

_MIGRATION_LOCK = 4_202_609  # произвольный номер advisory-блокировки


class PostgresStore:
    name = "postgres"

    def __init__(self, url: str, *, max_size: int = 4) -> None:
        self._pool = ConnectionPool(
            url,
            min_size=1,
            max_size=max_size,
            # Neon засыпает и рвёт простаивающие соединения: проверяем перед выдачей.
            check=ConnectionPool.check_connection,
            max_idle=240,
            # Пулер Neon (PgBouncer) не любит серверные prepared statements.
            kwargs={"prepare_threshold": None},
            name="bugin",
            open=True,
        )
        self._lock = threading.Lock()
        self._revision = 0
        self.migrate()

    def close(self) -> None:
        self._pool.close()

    @property
    def revision(self) -> int:
        return self._revision

    def _bump(self) -> None:
        with self._lock:
            self._revision += 1

    def migrate(self) -> int:
        """Применяет новые миграции; возвращает номер версии схемы."""
        with self._pool.connection() as conn:
            conn.execute("select pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
            conn.execute("create table if not exists schema_version (version integer not null)")
            row = conn.execute("select coalesce(max(version), 0) from schema_version").fetchone()
            current = row[0] if row else 0
            for number, statements in enumerate(MIGRATIONS, start=1):
                if number <= current:
                    continue
                for statement in statements:
                    conn.execute(statement)
                conn.execute("insert into schema_version (version) values (%s)", (number,))
                current = number
        return current

    def ping(self) -> bool:
        with self._pool.connection() as conn:
            return conn.execute("select 1").fetchone() == (1,)

    # ---------- Каталог ----------

    @staticmethod
    def _record(kind: str, row: tuple) -> Record:
        item_id, doc, published, demo, updated_at = row
        return Record(kind=kind, id=item_id, doc=doc, published=published, demo=demo, updated_at=updated_at)

    def records(self, kind: str) -> list[Record]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "select id, doc, published, demo, updated_at from catalog_items"
                " where kind = %s order by seq",
                (check_kind(kind),),
            ).fetchall()
        return [self._record(kind, row) for row in rows]

    def get(self, kind: str, item_id: str) -> Record | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "select id, doc, published, demo, updated_at from catalog_items"
                " where kind = %s and id = %s",
                (check_kind(kind), item_id),
            ).fetchone()
        return None if row is None else self._record(kind, row)

    def save(self, kind: str, item_id: str, doc: dict, *, published: bool, demo: bool = False) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                insert into catalog_items (kind, id, doc, published, demo)
                values (%s, %s, %s, %s, %s)
                on conflict (kind, id) do update set
                    doc = excluded.doc,
                    published = excluded.published,
                    demo = excluded.demo,
                    updated_at = now()
                """,
                (check_kind(kind), item_id, Jsonb({**doc, "id": item_id}), published, demo),
            )
        self._bump()

    def delete(self, kind: str, item_id: str) -> bool:
        with self._pool.connection() as conn:
            row = conn.execute(
                "delete from catalog_items where kind = %s and id = %s returning id",
                (check_kind(kind), item_id),
            ).fetchone()
        self._bump()
        return row is not None

    def delete_demo(self) -> int:
        with self._pool.connection() as conn:
            rows = conn.execute("delete from catalog_items where demo returning id").fetchall()
        self._bump()
        return len(rows)

    # ---------- Фото ----------

    def save_image(self, image_id: str, content_type: str, data: bytes, width: int, height: int) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "insert into images (id, content_type, data, width, height)"
                " values (%s, %s, %s, %s, %s)",
                (image_id, content_type, data, width, height),
            )

    def image(self, image_id: str) -> StoredImage | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "select data, content_type from images where id = %s", (image_id,)
            ).fetchone()
        return None if row is None else StoredImage(data=bytes(row[0]), content_type=row[1])

    def delete_images(self, image_ids: list[str]) -> None:
        if not image_ids:
            return
        with self._pool.connection() as conn:
            conn.execute("delete from images where id = any(%s)", (list(image_ids),))

    # ---------- Служебные отметки ----------

    def flag(self, key: str) -> str | None:
        with self._pool.connection() as conn:
            row = conn.execute("select value from flags where key = %s", (key,)).fetchone()
        return None if row is None else row[0]

    def set_flag(self, key: str, value: str) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "insert into flags (key, value) values (%s, %s)"
                " on conflict (key) do update set value = excluded.value",
                (key, value),
            )
