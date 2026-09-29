"""Настройки сервера из переменных окружения (на Render — раздел Environment).

- ``DATABASE_URL`` — строка подключения PostgreSQL (Neon). Нет — каталог в памяти
  с тестовыми данными, правки в админке пропадают при перезапуске.
- ``ADMIN_PASSWORD`` — пароль админки ``/admin``. Нет — админка выключена.
- ``PUBLIC_URL`` — внешний адрес сервера для ссылок на фото. На Render не нужен:
  там есть ``RENDER_EXTERNAL_URL``.
- ``SEED_DEMO`` — ``0``, чтобы не заводить тестовые данные в пустую базу.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    admin_password: str
    public_url: str
    seed_demo: bool


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def load() -> Settings:
    public_url = _env("PUBLIC_URL") or _env("RENDER_EXTERNAL_URL")
    return Settings(
        database_url=_env("DATABASE_URL"),
        admin_password=os.environ.get("ADMIN_PASSWORD", ""),
        public_url=public_url.rstrip("/"),
        seed_demo=_env("SEED_DEMO") not in ("0", "false", "no"),
    )
