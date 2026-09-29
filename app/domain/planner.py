"""«Собрать мне вечер» — перенос ``MockEveningPlanner``.

Шаблон по настроению → перебор вариантов в рамках бюджета → расписание
с переездами и округлением до 15 минут. Тексты плана — на языке ответа.
Работает с dict в формате контракта: ``EveningRequest``, ``Scenario``,
``PlanStop``, ``TravelLeg``.
"""

import time
from datetime import datetime
from typing import NamedTuple

from app.domain import geo
from app.domain.texts import dart_round, kind_label, plan_title, t

COMPANIES = ("solo", "pair", "friends", "family")
PLAN_DAYS = ("today", "tomorrow", "weekend", "date")
MOODS = ("calm", "active", "novelty", "culture")
STOP_ROLES = ("coffee", "walk", "dinner", "activity", "culture", "novelty", "work")
TRAVEL_MODES = ("walk", "taxi")

CALM_EVENING_ID = "calm_evening_pair"
WORK_DAY_ID = "work_day"
ACTIVE_SATURDAY_ID = "active_saturday"

SCENARIO_EVENING_IMAGE = "assets/images/scenario_evening.jpg"
SCENARIO_WORK_DAY_IMAGE = "assets/images/scenario_work_day.jpg"


class Candidate(NamedTuple):
    """Вариант для роли в плане."""

    place_id: str
    kind: str  # код занятия, см. texts.kind_label
    duration_minutes: int
    cost: int | None = None  # None — средний чек места


_TEMPLATES: dict[str, list[str]] = {
    "calm": ["coffee", "walk", "dinner"],
    "active": ["activity", "dinner"],
    "novelty": ["novelty", "walk", "dinner"],
    "culture": ["culture", "walk", "dinner"],
}

# Кто подходит на роль в плане: (категория места, код занятия, минуты, ярус).
# Внутри роли места идут по ярусу, затем по рейтингу и близости — планировщик
# предпочитает первых. Так план собирается из любого каталога, не из списка id.
_ROLE_OPTIONS: dict[str, list[tuple[str, str, int, int]]] = {
    "coffee": [("coffeeShop", "coffee", 60, 0), ("cafe", "coffee", 60, 1)],
    "walk": [("park", "walk", 45, 0)],
    "dinner": [("cafe", "dinner", 105, 0), ("restaurant", "dinner", 105, 0)],
    "activity": [("bowling", "bowling", 120, 0), ("cinema", "cinema", 150, 0)],
    "culture": [("gallery", "exhibition", 75, 0), ("cinema", "cinema", 150, 1)],
    "novelty": [("studio", "workshop", 120, 0), ("bowling", "bowling", 120, 1)],
    "work": [("coffeeShop", "coffee_work", 240, 0), ("cafe", "coffee_work", 240, 1)],
}

# Сколько вариантов на роль перебирать: 3 роли × 5 вариантов — мгновенно.
MAX_PER_ROLE = 5

# Рабочий день: кроме чека — ещё один напиток за четыре часа.
_WORK_EXTRA = 500


def _role_candidates(role: str, places: list[dict]) -> list[Candidate]:
    options = {category: (kind, minutes, tier) for category, kind, minutes, tier in _ROLE_OPTIONS.get(role, [])}
    ranked = []
    for place in places:
        option = options.get(place["category"])
        if option is None:
            continue
        kind, minutes, tier = option
        amenities = {a.get("type") for a in place.get("amenities") or []}
        if role == "work" and not {"wifi", "sockets"} <= amenities:
            continue
        if kind == "dinner" and place["category"] == "restaurant" and "beautiful" in place["vibes"]:
            kind = "dinner_view"
        cost = place["averageCheck"] + _WORK_EXTRA if role == "work" else None
        ranked.append(((tier, -place["rating"], place["distanceKm"]), Candidate(place["id"], kind, minutes, cost)))
    ranked.sort(key=lambda item: item[0])
    return [candidate for _, candidate in ranked[:MAX_PER_ROLE]]


_NO_CINEMA_PHRASES = ("без кино", "киносыз", "кино емес", "кинодан басқа", "кино керек емес")


# ---------- JSON → dict с умолчаниями (как fromJson в приложении) ----------


def _choice(value: object, allowed: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _int_or(value: object, default: int | None) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _iso_date(value: object) -> str | None:
    """Дата плана как ``YYYY-MM-DDT00:00:00``; непонятная строка → None (``DateTime.tryParse``)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment.replace(tzinfo=None).isoformat(timespec="seconds")


def default_request(**changes: object) -> dict:
    """``EveningRequest()`` с умолчаниями конструктора: вдвоём, сегодня, 19:00, 15 000, спокойно."""
    request = {
        "company": "pair",
        "day": "today",
        "date": None,
        "startMinutes": 19 * 60,
        "budget": 15000,
        "mood": "calm",
        "wishes": "",
    }
    request.update(changes)
    return request


def request_from_json(raw: dict) -> dict:
    """``EveningRequest.fromJson``: неизвестные коды → умолчания, нет бюджета → «не важен»."""
    wishes = raw.get("wishes")
    return {
        "company": _choice(raw.get("company"), COMPANIES, "pair"),
        "day": _choice(raw.get("day"), PLAN_DAYS, "today"),
        "date": _iso_date(raw.get("date")),
        "startMinutes": _int_or(raw.get("startMinutes"), 19 * 60),
        "budget": _int_or(raw.get("budget"), None),
        "mood": _choice(raw.get("mood"), MOODS, "calm"),
        "wishes": wishes if isinstance(wishes, str) else "",
    }


def stop_from_json(raw: dict) -> dict:
    """``PlanStop.fromJson``."""
    rating = raw.get("rating")
    return {
        "role": _choice(raw.get("role"), STOP_ROLES, "activity"),
        "placeId": str(raw["placeId"]),
        "kind": raw.get("kind") or "",
        "title": raw.get("title") or "",
        "kindLabel": raw.get("kindLabel") or "",
        "startMinutes": _int_or(raw.get("startMinutes"), 0),
        "durationMinutes": _int_or(raw.get("durationMinutes"), 60),
        "cost": _int_or(raw.get("cost"), 0),
        "routeLabel": raw.get("routeLabel"),
        "rating": float(rating) if isinstance(rating, (int, float)) else None,
        "image": raw.get("image") or "",
    }


def scenario_from_json(raw: dict) -> dict:
    """``Scenario.fromJson``."""
    request = raw.get("request")
    return {
        "id": str(raw["id"]),
        "title": raw.get("title") or "",
        "subtitle": raw.get("subtitle"),
        "image": raw.get("image"),
        "stops": [stop_from_json(s) for s in raw.get("stops") or []],
        "legs": [
            {
                "mode": _choice(leg.get("mode"), TRAVEL_MODES, "taxi"),
                "minutes": _int_or(leg.get("minutes"), 10),
            }
            for leg in raw.get("legs") or []
        ],
        "tags": [str(tag) for tag in raw.get("tags") or []],
        "request": request_from_json(request) if isinstance(request, dict) else None,
    }


def total_cost(scenario: dict) -> int:
    return sum(stop["cost"] for stop in scenario["stops"])


def _scenario(
    scenario_id: str,
    title: str,
    stops: list[dict],
    legs: list[dict],
    subtitle: str | None = None,
    image: str | None = None,
    tags: list[str] | None = None,
    request: dict | None = None,
) -> dict:
    return {
        "id": scenario_id,
        "title": title,
        "subtitle": subtitle,
        "image": image,
        "stops": stops,
        "legs": legs,
        "tags": tags or [],
        "request": request,
    }


def _round_up_15(minutes: int) -> int:
    return (minutes + 14) // 15 * 15


def _at_least_5(minutes: int) -> int:
    return max(minutes, 5)


# ---------- Планировщик ----------


class EveningPlanner:
    """Сборка и правка планов на одном языке по снимку мест."""

    def __init__(self, lang: str, places: list[dict]):
        self.lang = lang
        self._places = {p["id"]: p for p in places}
        self._candidates = {role: _role_candidates(role, places) for role in _ROLE_OPTIONS}

    def _t(self, ru: str, kk: str) -> str:
        return t(self.lang, ru, kk)

    def _place(self, place_id: str) -> dict | None:
        return self._places.get(place_id)

    # ----- Публичные операции -----

    def plan(self, request: dict, plan_id: str | None = None) -> dict:
        """Новый план по ``EveningRequest``. ``request`` — уже с умолчаниями."""
        if plan_id is None:
            plan_id = f"plan_{int(time.time() * 1000)}"
        return self._compose(request, plan_id)

    def featured(self, now: datetime) -> dict:
        """«Для тебя сегодня»: до 16:00 — рабочий день (если есть подходящая кофейня),
        потом — спокойный вечер вдвоём."""
        if now.hour < 16 and self._candidates["work"]:
            return self._work_day()
        return self._compose(default_request(), CALM_EVENING_ID, image=SCENARIO_EVENING_IMAGE)

    def library(self) -> list[dict]:
        """Готовые сценарии (для избранного и главной); без мест для них — меньше."""
        result = [self._compose(default_request(), CALM_EVENING_ID, image=SCENARIO_EVENING_IMAGE)]
        if self._candidates["work"]:
            result.append(self._work_day())
        result.append(self._compose(self._active_saturday_request(), ACTIVE_SATURDAY_ID))
        return [scenario for scenario in result if scenario["stops"]]

    def localize(self, scenario: dict) -> dict:
        """Тот же план (точки, время, цены), но тексты — на языке ответа."""
        stops = [self._relabel(stop) for stop in scenario["stops"]]
        request = scenario["request"]
        if scenario["id"] == WORK_DAY_ID:
            return {**self._work_day(), "stops": stops, "legs": scenario["legs"]}
        if scenario["id"] == ACTIVE_SATURDAY_ID:
            return {**scenario, "title": self._active_saturday_title(), "stops": stops}
        if request is not None:
            title = plan_title(self.lang, request["mood"], request["company"])
            return {**scenario, "title": title, "stops": stops}
        return {**scenario, "stops": stops}

    def alternatives(self, scenario: dict, index: int) -> list[dict]:
        """Замены точки ``index`` в рамках бюджета, без мест, которые уже есть в плане."""
        current = _stop_at(scenario, index)
        request = scenario["request"]
        budget = request["budget"] if request is not None else None
        spent_without = total_cost(scenario) - current["cost"]
        no_cinema = _no_cinema(request)
        used = {stop["placeId"] for stop in scenario["stops"]}
        result = []
        for candidate in self._all_candidates_for(current["role"]):
            if candidate.place_id in used:
                continue
            stop = self._to_stop(current["role"], candidate, current["startMinutes"])
            if stop is None:
                continue
            if no_cinema and self._is_cinema(stop["placeId"]):
                continue
            if budget is not None and spent_without + stop["cost"] > budget:
                continue
            result.append(stop)
        return result

    def replace_stop(self, scenario: dict, index: int, stop: dict) -> dict:
        """Ставит ``stop`` на место ``index`` и пересчитывает время и переезды."""
        _stop_at(scenario, index)
        start = scenario["stops"][0]["startMinutes"]
        stops = list(scenario["stops"])
        stops[index] = stop
        scheduled, legs = self._schedule(stops, start)
        return {**scenario, "stops": scheduled, "legs": legs}

    # ----- Сборка -----

    def _active_saturday_request(self) -> dict:
        return default_request(company="friends", day="weekend", startMinutes=18 * 60, mood="active")

    def _active_saturday_title(self) -> str:
        return self._t("Активная суббота", "Белсенді сенбі")

    def _compose(self, request: dict, scenario_id: str, image: str | None = None) -> dict:
        roles = _TEMPLATES.get(request["mood"]) or _TEMPLATES["calm"]
        chosen = self._choose(roles, request["budget"], _no_cinema(request))
        stops, legs = self._schedule(chosen, request["startMinutes"])
        if scenario_id == ACTIVE_SATURDAY_ID:
            title = self._active_saturday_title()
        else:
            title = plan_title(self.lang, request["mood"], request["company"])
        return _scenario(scenario_id, title, stops, legs, image=image, request=request)

    def _choose(self, roles: list[str], budget: int | None, no_cinema: bool) -> list[dict]:
        """Перебирает варианты по ролям (их немного) и берёт план с наибольшим числом
        точек в рамках бюджета; при равенстве — с более предпочтительными местами."""
        best: list[dict] = []
        best_penalty = 1 << 30

        def search(i: int, chosen: list[dict], spent: int, penalty: int) -> None:
            nonlocal best, best_penalty
            if i == len(roles):
                better = len(chosen) > len(best) or (
                    len(chosen) == len(best) and penalty < best_penalty
                )
                if better:
                    best = list(chosen)
                    best_penalty = penalty
                return
            for c, candidate in enumerate(self._candidates.get(roles[i], [])):
                if no_cinema and self._is_cinema(candidate.place_id):
                    continue
                if any(s["placeId"] == candidate.place_id for s in chosen):
                    continue
                stop = self._to_stop(roles[i], candidate, 0)
                if stop is None:
                    continue
                if budget is not None and spent + stop["cost"] > budget:
                    continue
                chosen.append(stop)
                search(i + 1, chosen, spent + stop["cost"], penalty + c)
                chosen.pop()
            # Вариант «пропустить эту роль».
            search(i + 1, chosen, spent, penalty + 10)

        search(0, [], 0, 0)
        return best

    def _work_day(self) -> dict:
        candidates = self._candidates["work"]
        if not candidates:
            raise LookupError("В каталоге нет кофейни с Wi-Fi и розетками")
        stop = self._to_stop("work", candidates[0], 10 * 60)
        if stop is None:
            raise LookupError(f"В каталоге нет места {candidates[0].place_id}")
        return _scenario(
            WORK_DAY_ID,
            self._t("Спокойный день", "Тыныш күн"),
            [stop],
            [],
            subtitle=self._t("Кофейня → работа", "Кофехана → жұмыс"),
            image=SCENARIO_WORK_DAY_IMAGE,
            tags=["Wi-Fi", self._t("Розетки", "Розеткалар"), self._t("Тихо", "Тыныш")],
        )

    def _to_stop(self, role: str, candidate: Candidate, start: int) -> dict | None:
        place = self._place(candidate.place_id)
        if place is None:
            return None
        is_free = place["averageCheck"] == 0
        return {
            "role": role,
            "placeId": place["id"],
            "kind": candidate.kind,
            "title": place["name"],
            "kindLabel": kind_label(self.lang, candidate.kind),
            "startMinutes": start,
            "durationMinutes": candidate.duration_minutes,
            "cost": candidate.cost if candidate.cost is not None else place["averageCheck"],
            "routeLabel": self._route_label(place),
            "rating": None if is_free else place["rating"],
            "image": place["photos"][0] if place["photos"] else "",
        }

    def _relabel(self, stop: dict) -> dict:
        place = self._place(stop["placeId"])
        if place is None:
            return stop
        return {
            **stop,
            "title": place["name"],
            "kindLabel": kind_label(self.lang, stop["kind"]),
            "routeLabel": self._route_label(place),
        }

    def _route_label(self, place: dict) -> str | None:
        return self._t("набережная", "жағалау") if place["category"] == "park" else None

    def _schedule(self, stops: list[dict], start: int) -> tuple[list[dict], list[dict]]:
        """Расставляет время: старт → длительность → переезд → округление до 15 минут."""
        result: list[dict] = []
        legs: list[dict] = []
        moment = start
        for i, stop in enumerate(stops):
            placed = {**stop, "startMinutes": moment}
            result.append(placed)
            moment = placed["startMinutes"] + placed["durationMinutes"]
            if i < len(stops) - 1:
                leg = self._leg(stop["placeId"], stops[i + 1]["placeId"])
                legs.append(leg)
                moment = _round_up_15(moment + leg["minutes"])
        return result, legs

    def _leg(self, from_id: str, to_id: str) -> dict:
        """Переезд: пешком до 0,8 км по городу, иначе такси. Путь по улицам — прямая × 1,3."""
        origin = self._place(from_id)
        target = self._place(to_id)
        if origin is None or target is None:
            return {"mode": "taxi", "minutes": 10}
        a, b = geo.point(origin.get("location")), geo.point(target.get("location"))
        if a is not None and b is not None:
            km = geo.distance_km(a, b) * 1.3
        else:
            km = abs(origin["distanceKm"] - target["distanceKm"]) + 0.3
        if km <= 0.8:
            return {"mode": "walk", "minutes": _at_least_5(dart_round(km * 12))}
        return {"mode": "taxi", "minutes": _at_least_5(dart_round(km * 3 + 4))}

    def _all_candidates_for(self, role: str) -> list[Candidate]:
        result = list(self._candidates.get(role, []))
        # Для активностей и культуры можно предложить и «что-то новое».
        if role in ("activity", "culture"):
            result += self._candidates["novelty"]
        return result

    def _is_cinema(self, place_id: str) -> bool:
        place = self._place(place_id)
        return place is not None and place["category"] == "cinema"


def _stop_at(scenario: dict, index: int) -> dict:
    stops = scenario["stops"]
    if not 0 <= index < len(stops):
        raise IndexError(f"В плане нет точки с номером {index}")
    return stops[index]




def _no_cinema(request: dict | None) -> bool:
    wishes = (request or {}).get("wishes") or ""
    wishes = wishes.lower()
    return any(phrase in wishes for phrase in _NO_CINEMA_PHRASES)
