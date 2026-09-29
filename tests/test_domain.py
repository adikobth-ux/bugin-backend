"""Логика без веб-слоя: данные, поиск, «Собрать мне вечер».

Запуск без зависимостей: ``python -m unittest discover -s tests``.
Правила и ожидания — те же, что в тестах приложения (``test/widget_test.dart``).
"""

import random
import unittest
from datetime import datetime

from app.domain import catalog_data, texts
from app.domain.catalog import Catalog, starts_at
from app.domain.planner import (
    ACTIVE_SATURDAY_ID,
    WORK_DAY_ID,
    EveningPlanner,
    default_request,
    request_from_json,
    scenario_from_json,
    total_cost,
)
from app.domain.search import SearchService, parse
from app.storage import demo
from app.storage.memory import MemoryStore

# Вторник, полдень: ближайшая суббота — 3 октября, воскресенье — 4 октября.
NOW = datetime(2026, 9, 29, 12, 0)
EVENING = datetime(2026, 9, 29, 18, 30)


def demo_catalog(now: datetime = NOW) -> Catalog:
    """Каталог с тестовыми данными прототипа, как на свежем сервере."""
    store = MemoryStore()
    demo.seed(store, now)
    return Catalog(store)


catalog = demo_catalog()


def params(intent: dict) -> dict:
    return {p["type"]: p for p in intent["params"]}


class TextsTest(unittest.TestCase):
    def test_numbers_like_the_app(self):
        nbsp = "\u00a0"
        self.assertEqual(texts.tenge(6000), f"6{nbsp}000{nbsp}₸")
        self.assertEqual(texts.approx_tenge(12000), f"≈{nbsp}12{nbsp}000{nbsp}₸")
        self.assertEqual(texts.distance(1.5), f"1,5{nbsp}км")
        self.assertEqual(texts.distance(0.4), f"400{nbsp}м")
        self.assertEqual(texts.dart_round(2.5), 3)
        self.assertEqual(texts.try_int("any"), None)
        self.assertEqual(texts.try_int("15000"), 15000)

    def test_plan_titles(self):
        self.assertEqual(texts.plan_title("ru", "calm", "pair"), "Спокойный вечер вдвоём")
        self.assertEqual(texts.plan_title("kk", "calm", "pair"), "Екеуге арналған тыныш кеш")


class CatalogTest(unittest.TestCase):
    def test_eight_places_and_events_on_both_languages(self):
        for lang in ("ru", "kk"):
            self.assertEqual(len(catalog.places(lang)), 8)
            self.assertEqual(len(catalog.events(lang)), 8)

    def test_ids_do_not_depend_on_language(self):
        ru = [p["id"] for p in catalog.places("ru")]
        kk = [p["id"] for p in catalog.places("kk")]
        self.assertEqual(ru, kk)
        self.assertNotEqual(
            catalog.place("ru", catalog_data.ESIL_EMBANKMENT)["name"],
            catalog.place("kk", catalog_data.ESIL_EMBANKMENT)["name"],
        )

    def test_nearby_is_closest_first(self):
        nearby = catalog.nearby("ru", 3)
        self.assertEqual(len(nearby), 3)
        distances = [p["distanceKm"] for p in nearby]
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(nearby[0]["id"], catalog_data.ESIL_EMBANKMENT)

    def test_nearby_from_the_user_location(self):
        gallery = catalog.place("ru", catalog_data.BASTAU_GALLERY)["location"]
        first = catalog.nearby("ru", 1, origin=(gallery["lat"], gallery["lng"]))[0]
        self.assertEqual(first["id"], catalog_data.BASTAU_GALLERY)
        self.assertEqual(first["distanceKm"], 0.0)

    def test_distances_from_the_user_and_not_from_another_city(self):
        gallery = catalog.place("ru", catalog_data.BASTAU_GALLERY)["location"]
        user = (gallery["lat"], gallery["lng"])
        self.assertEqual(catalog.place("ru", catalog_data.BASTAU_GALLERY, user)["distanceKm"], 0.0)
        self.assertEqual(catalog.place("ru", catalog_data.BASTAU_GALLERY, user)["taxiMinutes"], 3)
        moved = {e["id"]: e["distanceKm"] for e in catalog.events("ru", user)}
        self.assertNotEqual(moved, {e["id"]: e["distanceKm"] for e in catalog.events("ru")})
        # Из Алматы Астану смотрят как обычно — от центра.
        almaty = (43.238, 76.945)
        self.assertEqual(catalog.places("ru", almaty), catalog.places("ru"))
        self.assertEqual(catalog.events("kk", almaty), catalog.events("kk"))

    def test_by_ids_keeps_order_and_skips_unknown(self):
        ids = [catalog_data.SKY_LOUNGE, "nope", catalog_data.THE_GARDEN]
        found = [p["id"] for p in catalog.places_by_ids("ru", ids)]
        self.assertEqual(found, [catalog_data.SKY_LOUNGE, catalog_data.THE_GARDEN])

    def test_event_days(self):
        today = [e["id"] for e in catalog.events_for_day("ru", NOW, "today")]
        self.assertIn(catalog_data.ROOFTOP_ACOUSTIC, today)
        starts = [starts_at(e) for e in catalog.events_for_day("ru", NOW, "today")]
        self.assertEqual(starts, sorted(starts))
        weekend = [e["id"] for e in catalog.events_for_day("ru", NOW, "weekend")]
        self.assertEqual(weekend, [catalog_data.NEON_NIGHTS, catalog_data.SEAGULL])
        tomorrow = {e["id"] for e in catalog.events_for_day("ru", NOW, "tomorrow")}
        self.assertEqual(tomorrow, {catalog_data.JAZZ, catalog_data.STANDUP})

    def test_dates_are_local_without_offset(self):
        neon = catalog.event("ru", catalog_data.NEON_NIGHTS)
        self.assertEqual(neon["startsAt"], "2026-10-03T20:00:00")

    def test_tickets_are_links_to_operators(self):
        for e in catalog.events("ru"):
            self.assertTrue(
                e["ticketUrl"].startswith(("https://ticketon.kz/", "https://kino.kz/")), e["id"]
            )
        cinema = catalog.place("ru", catalog_data.LUNA_CINEMA)
        self.assertEqual(cinema["bookingUrl"], "https://kino.kz/ru/movie")

    def test_similar_events_first_same_category(self):
        similar = catalog.similar_events("ru", NOW, catalog_data.NEON_NIGHTS)
        self.assertNotIn(catalog_data.NEON_NIGHTS, [e["id"] for e in similar])
        self.assertEqual(similar[0]["category"], "concert")


class SearchTest(unittest.TestCase):
    def test_parses_the_query_from_the_spec(self):
        intent = parse(
            "Хочу сегодня вечером сходить куда-нибудь с девушкой, "
            "чтобы было красиво и не слишком дорого",
            NOW,
        )
        p = params(intent)
        self.assertEqual(p["occasion"]["code"], "date")
        self.assertEqual(p["time"]["code"], "evening")
        self.assertEqual(p["budget"]["code"], "15000")
        self.assertEqual(p["mood"]["code"], "beautiful")
        self.assertTrue(p["location"]["inferred"])

    def test_understands_kazakh(self):
        p = params(parse("Кешке қызбен әдемі жерге, 10 мыңға дейін", NOW))
        self.assertEqual(p["occasion"]["code"], "date")
        self.assertEqual(p["time"]["code"], "evening")
        self.assertEqual(p["budget"]["code"], "10000")
        self.assertEqual(p["mood"]["code"], "beautiful")

    def test_time_is_not_budget(self):
        p = params(parse("кафе в 19:00 до 10 000 тенге", NOW))
        self.assertEqual(p["budget"]["code"], "10000")

    def test_inferred_time_depends_on_hour(self):
        self.assertEqual(params(parse("кофе", NOW))["time"]["code"], "day")
        self.assertEqual(params(parse("кофе", EVENING))["time"]["code"], "evening")

    def test_ranking_respects_budget_and_explains_in_language(self):
        intent = parse("свидание до 5000", NOW)
        ru = SearchService("ru", catalog.places("ru"), catalog.events("ru"))
        kk = SearchService("kk", catalog.places("kk"), catalog.events("kk"))
        items = ru.rank(intent, NOW)
        self.assertTrue(items)
        for item in items:
            price = item["place"]["averageCheck"] if item["place"] else item["event"]["priceFrom"]
            self.assertLessEqual(price, 5000)
        kk_items = kk.rank(intent, NOW)
        self.assertEqual(
            [i["kind"] + (i["place"] or i["event"])["id"] for i in kk_items],
            [i["kind"] + (i["place"] or i["event"])["id"] for i in items],
        )
        self.assertNotEqual(kk_items[0]["reason"], items[0]["reason"])

    def test_ranking_is_sorted_and_has_no_parks(self):
        service = SearchService("ru", catalog.places("ru"), catalog.events("ru"))
        items = service.rank({"query": "", "params": []}, NOW)
        scores = [i["score"] for i in items]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertNotIn("park", [i["place"]["category"] for i in items if i["place"]])

    def test_surprise_picks_from_ranking(self):
        service = SearchService("ru", catalog.places("ru"), catalog.events("ru"))
        item = service.surprise(NOW, random.Random(1))
        self.assertIn(item["kind"], ("place", "event"))


class PlannerTest(unittest.TestCase):
    def setUp(self):
        self.ru = EveningPlanner("ru", catalog.places("ru"))
        self.kk = EveningPlanner("kk", catalog.places("kk"))

    def test_plan_fits_budget_for_every_mood(self):
        for budget in (5000, 10000, 15000):
            for mood in ("calm", "active", "novelty", "culture"):
                plan = self.ru.plan(default_request(budget=budget, mood=mood))
                self.assertLessEqual(total_cost(plan), budget, (mood, budget))
                self.assertTrue(plan["stops"])
                self.assertEqual(len(plan["legs"]), len(plan["stops"]) - 1)

    def test_times_are_rounded_to_15_minutes(self):
        plan = self.ru.plan(default_request())
        for stop in plan["stops"][1:]:
            self.assertEqual(stop["startMinutes"] % 15, 0)
        self.assertEqual(plan["stops"][0]["startMinutes"], 19 * 60)

    def test_title_reflects_company(self):
        plan = self.ru.plan(default_request(company="solo"))
        self.assertIn("для себя", plan["title"])

    def test_no_cinema_wish_in_both_languages(self):
        for wishes in ("без кино", "киносыз"):
            plan = self.ru.plan(default_request(mood="active", budget=None, wishes=wishes))
            self.assertNotIn(catalog_data.LUNA_CINEMA, [s["placeId"] for s in plan["stops"]])

    def test_alternatives_stay_within_budget_and_skip_used_places(self):
        plan = self.ru.plan(default_request(mood="active", budget=15000))
        alternatives = self.ru.alternatives(plan, 0)
        used = {s["placeId"] for s in plan["stops"]}
        spent_without = total_cost(plan) - plan["stops"][0]["cost"]
        for stop in alternatives:
            self.assertNotIn(stop["placeId"], used)
            self.assertLessEqual(spent_without + stop["cost"], 15000)

    def test_replace_recalculates_schedule(self):
        plan = self.ru.plan(default_request(mood="active", budget=None))
        alternatives = self.ru.alternatives(plan, 0)
        self.assertTrue(alternatives)
        replaced = self.ru.replace_stop(plan, 0, alternatives[0])
        self.assertEqual(replaced["stops"][0]["placeId"], alternatives[0]["placeId"])
        self.assertEqual(replaced["stops"][0]["startMinutes"], plan["stops"][0]["startMinutes"])

    def test_localize_keeps_stops_and_translates_texts(self):
        plan = self.ru.plan(default_request())
        translated = self.kk.localize(scenario_from_json(plan))
        self.assertEqual(translated["title"], "Екеуге арналған тыныш кеш")
        self.assertEqual(
            [s["placeId"] for s in translated["stops"]], [s["placeId"] for s in plan["stops"]]
        )
        self.assertEqual(total_cost(translated), total_cost(plan))
        self.assertNotEqual(translated["stops"][0]["kindLabel"], plan["stops"][0]["kindLabel"])

    def test_library_and_featured(self):
        ids = [s["id"] for s in self.ru.library()]
        self.assertEqual(ids, ["calm_evening_pair", WORK_DAY_ID, ACTIVE_SATURDAY_ID])
        self.assertEqual(self.ru.featured(NOW)["id"], WORK_DAY_ID)
        self.assertEqual(self.ru.featured(EVENING)["id"], "calm_evening_pair")

    def test_request_defaults_like_the_app(self):
        request = request_from_json({"mood": "unknown", "startMinutes": "19:00"})
        self.assertEqual(request["mood"], "calm")
        self.assertEqual(request["startMinutes"], 19 * 60)
        self.assertIsNone(request["budget"])


if __name__ == "__main__":
    unittest.main()
