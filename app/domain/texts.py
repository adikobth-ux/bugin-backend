"""Тексты и форматирование — перенос из приложения.

Источники: ``lib/core/formatters.dart`` (``Fmt``) и ``lib/l10n/app_strings.dart``
(``planTitle``); подписи занятий плана — ``MockEveningPlanner._kindLabel``.
Округление повторяет Dart: половина — от нуля, а не к чётному, как ``round`` в Python.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

# Неразрывный пробел: между разрядами, перед «₸», «км», «м».
NBSP = " "


def t(lang: str, ru: str, kk: str) -> str:
    """Текст на языке ответа: пара «русский, казахский»."""
    return kk if lang == "kk" else ru


# ---------- Числа ----------


def dart_round(value: float) -> int:
    """``double.round()`` из Dart: ближайшее целое, половина — от нуля (2.5 → 3)."""
    magnitude = abs(value)
    whole = math.floor(magnitude)
    if magnitude - whole >= 0.5:
        whole += 1
    return -whole if value < 0 else whole


def try_int(text: str | None) -> int | None:
    """``int.tryParse`` из Dart: целое со знаком или None («any», «», «1.5» → None)."""
    if text is None:
        return None
    s = text.strip()
    digits = s[1:] if s[:1] in "+-" else s
    if not digits or not all("0" <= c <= "9" for c in digits):
        return None
    return int(s)


# ---------- Fmt ----------


def thousands(value: int) -> str:
    """12000 → «12 000» (разделитель — неразрывный пробел)."""
    digits = str(abs(value))
    parts = []
    for i, digit in enumerate(digits):
        parts.append(digit)
        from_end = len(digits) - i
        if from_end > 1 and from_end % 3 == 1:
            parts.append(NBSP)
    text = "".join(parts)
    return f"-{text}" if value < 0 else text


def tenge(value: int) -> str:
    """6000 → «6 000 ₸»."""
    return f"{thousands(value)}{NBSP}₸"


def approx_tenge(value: int) -> str:
    """6000 → «≈ 6 000 ₸»."""
    return f"≈{NBSP}{tenge(value)}"


def decimal(value: float, digits: int = 1) -> str:
    """4.8 → «4,8». Как ``toStringAsFixed`` в Dart: половина — вверх по модулю."""
    quantum = Decimal(1).scaleb(-digits)
    fixed = Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)
    return f"{fixed:f}".replace(".", ",")


def distance(km: float) -> str:
    """1.5 → «1,5 км», 0.4 → «400 м». Сокращения одинаковые в обоих языках."""
    if km < 1:
        return f"{dart_round(km * 1000)}{NBSP}м"
    return f"{decimal(km)}{NBSP}км"


# ---------- Подписи плана ----------


def plan_title(lang: str, mood: str, company: str) -> str:
    """Название собранного плана: «Спокойный вечер вдвоём» / «Екеуге арналған тыныш кеш»."""
    if lang == "kk":
        who = {
            "solo": "Өзіңе арналған",
            "pair": "Екеуге арналған",
            "friends": "Достармен",
            "family": "Отбасымен",
        }[company]
        what = {
            "calm": "тыныш",
            "active": "белсенді",
            "novelty": "ерекше",
            "culture": "мәдени",
        }[mood]
        return f"{who} {what} кеш"
    what = {
        "calm": "Спокойный",
        "active": "Активный",
        "novelty": "Необычный",
        "culture": "Культурный",
    }[mood]
    who = {
        "solo": "для себя",
        "pair": "вдвоём",
        "friends": "с друзьями",
        "family": "с семьёй",
    }[company]
    return f"{what} вечер {who}"


_KIND_LABELS: dict[str, tuple[str, str]] = {
    "coffee": ("Кофе и десерт", "Кофе мен десерт"),
    "walk": ("Прогулка", "Серуен"),
    "dinner": ("Ужин", "Кешкі ас"),
    "dinner_view": ("Ужин с видом", "Көрінісі әдемі кешкі ас"),
    "bowling": ("Боулинг", "Боулинг"),
    "cinema": ("Кино", "Кино"),
    "exhibition": ("Выставка", "Көрме"),
    "workshop": ("Мастер-класс", "Шеберлік сабағы"),
    "coffee_work": ("Кофе и работа", "Кофе және жұмыс"),
}


def kind_label(lang: str, kind: str) -> str:
    """Подпись занятия по коду ``kind``; неизвестный код возвращается как есть."""
    pair = _KIND_LABELS.get(kind)
    if pair is None:
        return kind
    return t(lang, *pair)
