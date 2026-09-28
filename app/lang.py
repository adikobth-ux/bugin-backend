"""Язык ответа по заголовку Accept-Language."""

SUPPORTED = ("ru", "kk")
DEFAULT = "ru"


def from_header(accept_language: str | None) -> str:
    """Значение, начинающееся с «kk», → казахский, всё остальное → русский.

    >>> from_header("kk-KZ,ru;q=0.8")
    'kk'
    >>> from_header("ru-RU,kk;q=0.8")
    'ru'
    """
    if accept_language and accept_language.strip().lower().startswith("kk"):
        return "kk"
    return DEFAULT
