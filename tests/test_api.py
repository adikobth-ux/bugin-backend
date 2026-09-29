"""HTTP-слой: пути, языки, ошибки и соответствие контракту ``docs/api.md``.

Нужны зависимости из ``requirements-dev.txt``; без FastAPI тесты пропускаются.
Образцы ответов в ``tests/contract`` — те же файлы, что ``test/fixtures/api``
в приложении: если поле переименовать только на одной стороне, упадут тесты.
"""

import json
import os
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError as error:  # pragma: no cover - локально без зависимостей
    if os.environ.get("CI"):
        raise  # в CI зависимости обязаны быть: пропуск спрятал бы непроверенный сервер
    raise unittest.SkipTest(f"нет FastAPI: {error}") from error

from app import services
from app.main import app

CONTRACT = Path(__file__).parent / "contract"
KK = {"Accept-Language": "kk-KZ,kk;q=0.9,ru;q=0.8"}


def sample(name: str) -> object:
    return json.loads((CONTRACT / f"{name}.json").read_text(encoding="utf-8"))


def same_keys(test: unittest.TestCase, actual: object, expected: object, where: str = "$") -> None:
    """Ключи объектов совпадают на всех уровнях (null с одной стороны не сравнивается глубже)."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        test.assertEqual(set(actual), set(expected), where)
        for key in actual:
            if actual[key] is not None and expected[key] is not None:
                same_keys(test, actual[key], expected[key], f"{where}.{key}")
    elif isinstance(actual, list) and isinstance(expected, list) and actual and expected:
        same_keys(test, actual[0], expected[0], f"{where}[0]")


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def get(self, path: str, **kwargs):
        return self.client.get(path, **kwargs)

    def post(self, path: str, body: object, **kwargs):
        return self.client.post(path, json=body, **kwargs)

    # ---------- Служебное ----------

    def test_health_and_docs(self):
        self.assertEqual(self.get("/health").json(), {"status": "ok", "storage": "memory"})
        schema = self.get("/openapi.json").json()
        self.assertIn("/v1/search/understand", schema["paths"])

    def test_cors_allows_the_web_version(self):
        response = self.get(
            "/v1/places/nearby", headers={"Origin": "https://adikobth-ux.github.io"}
        )
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")

    def test_cors_preflight_for_json_post(self):
        # Браузер перед POST с JSON и языком спрашивает разрешения (OPTIONS).
        response = self.client.options(
            "/v1/search/understand",
            headers={
                "Origin": "https://adikobth-ux.github.io",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,accept-language",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("POST", response.headers.get("access-control-allow-methods", ""))

    def test_errors_follow_the_contract(self):
        response = self.get("/v1/places/nope")
        self.assertEqual(response.status_code, 404)
        same_keys(self, response.json(), sample("error_not_found"))
        self.assertEqual(response.json()["error"]["code"], "not_found")
        self.assertEqual(self.get("/v1/unknown").json()["error"]["code"], "not_found")
        bad = self.post("/v1/evening/plan", {"mood": "sleepy"})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.json()["error"]["code"], "bad_request")

    # ---------- Места ----------

    def test_places(self):
        nearby = self.get("/v1/places/nearby", params={"limit": 3}).json()
        self.assertEqual(len(nearby), 3)
        same_keys(self, nearby[0], sample("place"))
        garden = self.get("/v1/places/the_garden").json()
        self.assertEqual(garden["name"], "The Garden")
        found = self.get("/v1/places", params={"ids": "sky_lounge,nope,the_garden"}).json()
        self.assertEqual([p["id"] for p in found], ["sky_lounge", "the_garden"])

    def test_nearby_from_user_location(self):
        gallery = self.get("/v1/places/bastau_gallery").json()["location"]
        first = self.get(
            "/v1/places/nearby", params={"limit": 1, "lat": gallery["lat"], "lng": gallery["lng"]}
        ).json()[0]
        self.assertEqual((first["id"], first["distanceKm"]), ("bastau_gallery", 0.0))
        self.assertEqual(self.get("/v1/places/nearby", params={"lat": 91, "lng": 0}).status_code, 422)

    def test_user_location_header(self):
        gallery = self.get("/v1/places/bastau_gallery").json()["location"]
        here = {"X-Bugin-Location": f"{gallery['lat']},{gallery['lng']}"}
        self.assertEqual(self.get("/v1/places/bastau_gallery", headers=here).json()["distanceKm"], 0.0)
        first = self.get("/v1/places/nearby", params={"limit": 1}, headers=here).json()[0]
        self.assertEqual(first["id"], "bastau_gallery")
        plan = self.post("/v1/evening/plan", {"mood": "culture", "budget": None}, headers=here)
        self.assertEqual(plan.status_code, 200)
        found = self.post(
            "/v1/search/recommend", {"intent": {"query": "", "params": []}}, headers=here
        ).json()
        self.assertTrue(found)
        # Непонятный заголовок не ошибка: расстояния от центра.
        usual = self.get("/v1/places/bastau_gallery").json()["distanceKm"]
        for bad in ("abc", "51.1", "200,71", "nan,nan", "51.1,71.4,1"):
            response = self.get("/v1/places/bastau_gallery", headers={"X-Bugin-Location": bad})
            self.assertEqual(response.json()["distanceKm"], usual, bad)

    def test_cors_allows_the_location_header(self):
        response = self.client.options(
            "/v1/places/nearby",
            headers={
                "Origin": "https://adikobth-ux.github.io",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "accept-language,x-bugin-location",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("x-bugin-location", response.headers.get("access-control-allow-headers", "").lower())

    def test_admin_changes_are_served_at_once(self):
        store = services.store()
        store.save_image("0123abcd0123abcd", "image/jpeg", b"\xff\xd8test", 1, 1)
        store.save(
            "place", "mart",
            {"name": "Март", "category": "coffeeShop", "address": "пр. Мангилик Ел, 10",
             "averageCheck": 3500, "photos": ["/v1/images/0123abcd0123abcd.jpg"],
             "location": {"lat": 51.1282, "lng": 71.4404}},
            published=True,
        )
        try:
            mart = self.get("/v1/places/mart").json()
            same_keys(self, mart, sample("place"))
            self.assertEqual(mart["distanceKm"], 0.7)
            photo = self.get(mart["photos"][0].replace("http://testserver", ""))
            self.assertEqual(photo.content, b"\xff\xd8test")
            self.assertEqual(photo.headers["content-type"], "image/jpeg")
            self.assertIn("immutable", photo.headers["cache-control"])
        finally:
            store.delete("place", "mart")
        self.assertEqual(self.get("/v1/places/mart").status_code, 404)
        missing = self.get("/v1/images/ffffffffffffffff.jpg")
        self.assertEqual(missing.json()["error"]["code"], "not_found")
        self.assertEqual(self.get("/v1/images/..%2Fx.jpg").status_code, 404)

    def test_admin_is_mounted(self):
        response = self.get("/admin/login")
        self.assertIn(response.status_code, (200, 503))
        self.assertIn("text/html", response.headers["content-type"])
        self.assertNotIn("/admin/login", self.get("/openapi.json").json()["paths"])

    def test_language_from_header(self):
        ru = self.get("/v1/places/esil_embankment").json()
        kk = self.get("/v1/places/esil_embankment", headers=KK).json()
        self.assertEqual(ru["id"], kk["id"])
        self.assertNotEqual(ru["name"], kk["name"])

    # ---------- Афиша ----------

    def test_events(self):
        today = self.get("/v1/events", params={"day": "today"}).json()
        self.assertTrue(today)
        same_keys(self, today[0], sample("event"))
        starts = [e["startsAt"] for e in today]
        self.assertEqual(starts, sorted(starts))
        concerts = self.get("/v1/events", params={"day": "weekend", "category": "concert"}).json()
        self.assertTrue(all(e["category"] == "concert" for e in concerts))
        by_ids = self.get("/v1/events", params={"ids": "seagull_play,neon_nights"}).json()
        self.assertEqual([e["id"] for e in by_ids], ["seagull_play", "neon_nights"])
        self.assertEqual(self.get("/v1/events").status_code, 400)
        self.assertEqual(self.get("/v1/events/neon_nights").json()["id"], "neon_nights")
        similar = self.get("/v1/events/neon_nights/similar", params={"limit": 2}).json()
        self.assertEqual(len(similar), 2)
        self.assertEqual(self.get("/v1/events/nope/similar").status_code, 404)
        self.assertIsInstance(self.get("/v1/events/featured").json(), list)

    def test_ticket_links(self):
        neon = self.get("/v1/events/neon_nights").json()
        self.assertTrue(neon["ticketUrl"].startswith("https://ticketon.kz/"))

    # ---------- Поиск ----------

    def test_understand_and_recommend(self):
        intent = self.post(
            "/v1/search/understand", {"query": "Кешке қызбен әдемі жерге, 10 мыңға дейін"}
        ).json()
        same_keys(self, intent, sample("search_intent"))
        codes = {p["type"]: p["code"] for p in intent["params"]}
        self.assertEqual(codes["occasion"], "date")
        self.assertEqual(codes["budget"], "10000")

        items = self.post("/v1/search/recommend", {"intent": intent}, headers=KK).json()
        self.assertTrue(items)
        for item in items:
            price = item["place"]["averageCheck"] if item["place"] else item["event"]["priceFrom"]
            self.assertLessEqual(price, 10000)
        scores = [i["score"] for i in items]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_surprise(self):
        item = self.get("/v1/search/surprise").json()
        self.assertIn(item["kind"], ("place", "event"))

    # ---------- Вечер ----------

    def test_plan_and_edit(self):
        plan = self.post("/v1/evening/plan", sample("scenario")["request"]).json()
        same_keys(self, plan, sample("scenario"))
        self.assertEqual(plan["title"], "Спокойный вечер вдвоём")
        self.assertLessEqual(sum(s["cost"] for s in plan["stops"]), 15000)

        kk = self.post("/v1/evening/plan", {"company": "pair", "budget": 15000}, headers=KK).json()
        self.assertEqual(kk["title"], "Екеуге арналған тыныш кеш")

        alternatives = self.post(
            "/v1/evening/alternatives", {"scenario": plan, "index": 0}
        ).json()
        self.assertIsInstance(alternatives, list)
        if alternatives:
            replaced = self.post(
                "/v1/evening/replace",
                {"scenario": plan, "index": 0, "stop": alternatives[0]},
            ).json()
            self.assertEqual(replaced["stops"][0]["placeId"], alternatives[0]["placeId"])

        bad = self.post("/v1/evening/alternatives", {"scenario": plan, "index": 99})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["error"]["code"], "bad_request")

    def test_localize_saved_plan(self):
        saved = sample("scenario")
        translated = self.post("/v1/evening/localize", {"scenario": saved}, headers=KK).json()
        self.assertEqual(translated["title"], "Екеуге арналған тыныш кеш")
        self.assertEqual(
            [s["placeId"] for s in translated["stops"]], [s["placeId"] for s in saved["stops"]]
        )
        self.assertEqual(translated["stops"][1]["title"], "Есіл жағалауы")

    def test_featured_plan(self):
        plan = self.get("/v1/evening/featured").json()
        self.assertIn(plan["id"], ("work_day", "calm_evening_pair"))


if __name__ == "__main__":
    unittest.main()
