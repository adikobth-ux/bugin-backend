"""Местное время Казахстана.

С 2024 года в РК один часовой пояс — UTC+5, без перехода на летнее время,
поэтому хватает фиксированного смещения и не нужна база tzdata.
"""

from datetime import datetime, timedelta, timezone

KZ_TIMEZONE = timezone(timedelta(hours=5), "Asia/Almaty")


def now() -> datetime:
    """Текущее местное время как наивный datetime (без tzinfo), как в приложении."""
    return datetime.now(KZ_TIMEZONE).replace(tzinfo=None)
