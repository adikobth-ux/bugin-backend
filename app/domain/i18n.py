"""Двуязычные документы каталога.

Место и событие хранятся в формате контракта (``docs/api.md``), но любой текст может
быть парой ``{"ru": "…", "kk": "…"}`` — строкой или списком строк (теги).
``localize`` выбирает язык; пустой казахский заменяется русским, поэтому казахский
можно заполнять не сразу. ``merge`` собирает такой документ из двух одноязычных —
так в базу попадают тестовые данные.
"""

LANGS = ("ru", "kk")


def is_pair(value: object) -> bool:
    """``{"ru": …}`` или ``{"ru": …, "kk": …}`` — и ничего больше."""
    return isinstance(value, dict) and "ru" in value and set(value) <= set(LANGS)


def _empty(value: object) -> bool:
    return value is None or value == "" or value == []


def pick(pair: dict, lang: str) -> object:
    """Значение пары на языке ``lang``; пустое казахское → русское."""
    value = pair.get(lang)
    if _empty(value) and lang != "ru":
        value = pair.get("ru")
    return value if value is not None else ""


def localize(value: object, lang: str) -> object:
    """Документ целиком на одном языке. Исходный объект не меняется."""
    if is_pair(value):
        return localize(pick(value, lang), lang)
    if isinstance(value, dict):
        return {key: localize(item, lang) for key, item in value.items()}
    if isinstance(value, list):
        return [localize(item, lang) for item in value]
    return value


def text(value: object, lang: str = "ru") -> str:
    """Строка для показа (в админке): пара → язык, остальное → ``str``."""
    if is_pair(value):
        value = pick(value, lang)
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def pair(ru: object, kk: object) -> object:
    """Пара, если тексты различаются; иначе — просто значение."""
    if ru == kk or _empty(kk):
        return ru
    return {"ru": ru, "kk": kk}


def merge(ru: object, kk: object) -> object:
    """Два одноязычных документа одной структуры → двуязычный.

    Словари — по ключам, списки строк — парой списков (теги могут различаться
    числом), прочие списки — поэлементно, различающиеся строки — парой.
    """
    if ru == kk:
        return ru
    if isinstance(ru, dict) and isinstance(kk, dict) and set(ru) == set(kk):
        return {key: merge(ru[key], kk[key]) for key in ru}
    if isinstance(ru, list) and isinstance(kk, list):
        strings = all(isinstance(item, str) for item in ru + kk)
        if not strings and len(ru) == len(kk):
            return [merge(a, b) for a, b in zip(ru, kk, strict=True)]
        return {"ru": ru, "kk": kk}
    if isinstance(ru, str) and isinstance(kk, str):
        return {"ru": ru, "kk": kk}
    raise ValueError(f"Разная структура: {ru!r} и {kk!r}")
