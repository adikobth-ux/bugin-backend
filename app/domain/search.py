"""AI-поиск по правилам — перенос ``MockSearchService``.

Ключевые слова (русский и казахский) → параметры запроса, параметры → ранжирование
мест и событий. Объяснения пишутся на языке ответа. Всё работает с dict в формате
контракта: ``SearchIntent``, ``Place``, ``Event``, ``Recommendation``.
"""

import random
import re
from datetime import datetime

from app.domain import texts
from app.domain.catalog import day_diff, starts_at
from app.domain.texts import t

OCCASIONS = ("date", "friends", "work", "family", "solo")
VIBES = ("beautiful", "calm", "active", "novelty")
PARAM_TYPES = ("occasion", "time", "budget", "mood", "location")

# ---------- Понимание запроса ----------

_OCCASION_WORDS: list[tuple[str, list[str]]] = [
    ("date", ["девушк", "парн", "свидан", "вдвоем", "романт", "любим", "кездесу", "қызбен", "жігіт", "екеуміз", "сүйікті"]),  # noqa: E501
    ("friends", ["друз", "компани", "достар", "досым", "доспен"]),
    ("work", ["работ", "ноут", "розетк", "учеб", "позаниматься", "жұмыс", "оқу", "сабақ"]),
    ("family", ["семь", "детьми", "ребен", "родител", "отбасы", "бала", "ата-ана"]),
    ("solo", ["для себя", "одному", "одной", "өзім үшін", "жалғыз"]),
]

_TIME_WORDS: list[tuple[str, list[str]]] = [
    ("evening", ["вечер", "кешке", "кешт", "кешкі"]),
    ("morning", ["утр", "завтрак", "таңертең", "таңғы"]),
    ("day", ["днем", "обед", "күндіз", "түскі"]),
    ("night", ["ноч", "түнде", "түнгі"]),
]

_CHEAP_WORDS = ["недорог", "не дорог", "не слишком дорог", "дешев", "бюджетн", "эконом", "арзан", "қымбат емес", "үнемді"]  # noqa: E501
_LUXURY_WORDS = ["шикарн", "премиал", "не важно сколько", "сәнді", "премиум"]

_MOOD_WORDS: list[tuple[str, list[str]]] = [
    ("beautiful", ["красив", "романт", "панорам", "әдемі", "көрінісі"]),
    ("calm", ["спокой", "тих", "уют", "расслаб", "тыныш", "жайлы", "демал"]),
    ("active", ["актив", "спорт", "драйв", "весел", "подвига", "белсенді", "көңілді", "қозғал"]),
    ("novelty", ["нов", "необычн", "попробова", "удиви", "жаңа", "ерекше", "таң қалдыр"]),
]

_NEAR_WORDS = ["рядом", "недалеко", "поблизости", "возле", "жақын", "маңында", "қасында"]
_CENTER_WORDS = ["центр", "орталық"]

# «до 10 000», «10000 ₸», «15 тыс», «8к», «10 мың». Цифры — только ASCII, как \d в Dart;
# \s в Dart тоже ловит неразрывный пробел, здесь он указан явно.
_AMOUNT = re.compile(r"([0-9][0-9\s ]*[0-9]|[0-9])(\s*(тыс|мың|к|k))?")
_SPACES = re.compile(r"[\s ]")


def _param(param_type: str, code: str, inferred: bool = False) -> dict:
    return {"type": param_type, "code": code, "inferred": inferred}


def _first(q: str, table: list[tuple[str, list[str]]]) -> str | None:
    for code, words in table:
        if any(word in q for word in words):
            return code
    return None


def parse(query: str, now: datetime) -> dict:
    """Текст запроса → ``SearchIntent``. ``now`` нужен, чтобы додумать время суток."""
    q = query.lower().replace("ё", "е")

    def has(words: list[str]) -> bool:
        return any(word in q for word in words)

    params = []

    occasion = _first(q, _OCCASION_WORDS)
    if occasion is not None:
        params.append(_param("occasion", occasion))

    time = _first(q, _TIME_WORDS)
    if time is not None:
        params.append(_param("time", time))
    else:
        params.append(_param("time", "evening" if now.hour >= 16 else "day", inferred=True))

    amount = _amount(q)
    if amount is not None:
        params.append(_param("budget", str(amount)))
    elif has(_CHEAP_WORDS):
        params.append(_param("budget", "15000"))
    elif has(_LUXURY_WORDS):
        params.append(_param("budget", "any"))

    mood = _first(q, _MOOD_WORDS)
    if mood is not None:
        params.append(_param("mood", mood))

    if has(_NEAR_WORDS):
        params.append(_param("location", "near"))
    elif has(_CENTER_WORDS):
        params.append(_param("location", "center"))
    else:
        params.append(_param("location", "near", inferred=True))

    return {"query": query.strip(), "params": params}


def _amount(q: str) -> int | None:
    """Сумма в тенге из текста. Время вида «19:00» пропускается."""
    for match in _AMOUNT.finditer(q):
        end = match.end()
        if end < len(q) and q[end] == ":":
            continue
        value = int(_SPACES.sub("", match.group(1)))
        if match.group(3) is not None:
            value *= 1000
        if 1000 <= value <= 1000000:
            return value
    return None


# ---------- Подбор ----------


def _intent_param(intent: dict, param_type: str) -> dict | None:
    for p in intent.get("params") or []:
        if p.get("type") == param_type:
            return p
    return None


def _code(intent: dict, param_type: str) -> str | None:
    p = _intent_param(intent, param_type)
    return None if p is None else p.get("code")


def is_open_at_minute(hours: dict, minute: int) -> bool:
    """``OpeningHours.isOpenAtMinute``: ``closesAt`` > 1440 — работает после полуночи."""
    opens_at, closes_at = hours["opensAt"], hours["closesAt"]
    if opens_at == 0 and closes_at >= 1440:
        return True
    if closes_at <= 1440:
        return opens_at <= minute < closes_at
    return minute >= opens_at or minute < closes_at - 1440


_TARGET_MINUTE = {
    "morning": 10 * 60,
    "day": 14 * 60,
    "evening": 20 * 60,
    "night": 23 * 60 + 30,
}


class SearchService:
    """Подбор на одном языке по снимку каталога."""

    def __init__(self, lang: str, places: list[dict], events: list[dict]):
        self.lang = lang
        self._places = places
        self._events = events

    def _t(self, ru: str, kk: str) -> str:
        return t(self.lang, ru, kk)

    def rank(self, intent: dict, now: datetime) -> list[dict]:
        """``Recommendation[]`` по убыванию ``score``."""
        budget = texts.try_int(_code(intent, "budget"))
        occasion = _code(intent, "occasion")
        occasion = occasion if occasion in OCCASIONS else None
        vibe = _code(intent, "mood")
        vibe = vibe if vibe in VIBES else None
        time_code = _code(intent, "time")
        near = _code(intent, "location") == "near"
        target_minute = _TARGET_MINUTE.get(time_code) if time_code is not None else None

        result = []

        for place in self._places:
            if place["category"] == "park":
                continue
            if budget is not None and place["averageCheck"] > budget:
                continue
            if occasion is not None and occasion not in place["goodFor"]:
                continue
            if target_minute is not None and not is_open_at_minute(
                place["openingHours"], target_minute
            ):
                continue
            score = place["rating"] * 10
            if occasion is not None:
                score += 10
            if vibe is not None and vibe in place["vibes"]:
                score += 8
            if near:
                score -= place["distanceKm"] * 4
            result.append(
                {
                    "kind": "place",
                    "place": place,
                    "event": None,
                    "reason": _join(place["pitch"], self._budget_phrase(place["averageCheck"], budget)),
                    "details": self._place_details(place, occasion, budget),
                    "score": float(score),
                }
            )

        for event in self._events:
            start = starts_at(event)
            if day_diff(start, now) != 0:
                continue
            if budget is not None and event["priceFrom"] > budget:
                continue
            if occasion is not None and occasion not in event["occasions"]:
                continue
            long_running = event["durationMinutes"] >= 360
            if time_code == "evening" and start.hour < 17 and not long_running:
                continue
            if time_code == "morning" and start.hour >= 13 and not long_running:
                continue
            score = 40.0
            if occasion is not None:
                score += 10
            if vibe is not None and vibe in event["vibes"]:
                score += 8
            if near:
                score -= event["distanceKm"] * 4
            result.append(
                {
                    "kind": "event",
                    "place": None,
                    "event": event,
                    "reason": _join(event["pitch"], self._budget_phrase(event["priceFrom"], budget)),
                    "details": list(event["reasons"]),
                    "score": float(score),
                }
            )

        # Сортировка устойчивая: при равном счёте — порядок каталога, как в приложении.
        result.sort(key=lambda r: r["score"], reverse=True)
        return result

    def surprise(self, now: datetime, rng: random.Random | None = None) -> dict | None:
        """Случайный вариант из выдачи без фильтров; None — если выбирать не из чего."""
        pool = self.rank({"query": "", "params": []}, now)
        if not pool:
            return None
        return (rng or random).choice(pool)

    def _budget_phrase(self, price: int, budget: int | None) -> str | None:
        if budget is None:
            return None
        if price == 0:
            return self._t("бесплатно", "тегін")
        if price <= budget * 0.6:
            return self._t("дешевле твоего бюджета", "бюджетіңнен арзан")
        return self._t("в рамках бюджета", "бюджетке сай")

    def _place_details(self, p: dict, occasion: str | None, budget: int | None) -> list[str]:
        occasion_phrase = {
            "date": self._t("хорошо для свидания", "кездесуге жақсы"),
            "friends": self._t("удобно компанией", "достармен баруға ыңғайлы"),
            "work": self._t("можно спокойно поработать", "тыныш жұмыс істеуге болады"),
            "family": self._t("подойдёт всей семьёй", "бүкіл отбасыға лайық"),
            "solo": self._t("приятно провести время одному", "жалғыз уақыт өткізуге жақсы"),
        }.get(occasion) if occasion is not None else None

        details = [_join(p["pitch"], occasion_phrase)]
        if budget is not None:
            if p["averageCheck"] == 0:
                details.append(self._t("Бесплатно — бюджет не тратится", "Тегін — бюджет жұмсалмайды"))
            else:
                check = texts.approx_tenge(p["averageCheck"])
                limit = texts.tenge(budget)
                details.append(
                    self._t(
                        f"{check} на человека — в рамках твоих {limit}",
                        f"Бір адамға {check} — сенің {limit} бюджетіңе сай",
                    )
                )
        if p["bookingType"] == "table":
            details.append(self._t("Есть свободные столики сегодня с 19:00", "Бүгін 19:00-ден бос үстелдер бар"))
        else:
            km = texts.distance(p["distanceKm"])
            minutes = p["taxiMinutes"]
            details.append(
                self._t(
                    f"{km} от тебя · {minutes} мин на такси",
                    f"Саған дейін {km} · таксимен {minutes} мин",
                )
            )
        return details


def _join(base: str, tail: str | None) -> str:
    """«фишка — хвост» или «фишка — …, хвост», если тире уже есть."""
    if tail is None:
        return base
    return f"{base}, {tail}" if "—" in base else f"{base} — {tail}"
