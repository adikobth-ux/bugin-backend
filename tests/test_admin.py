"""Админка: вход, списки, создание, правка, фото, удаление — через HTTP, как с телефона.

Нужны Starlette, Jinja2, python-multipart, Pillow и httpx (есть в requirements-dev.txt).
"""

import io
import os
import unittest

try:
    from PIL import Image
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.testclient import TestClient
except ImportError as error:  # pragma: no cover - локально без зависимостей
    if os.environ.get("CI"):
        raise
    raise unittest.SkipTest(f"нет зависимостей админки: {error}") from error

from app import clock, config, services
from app.admin import app as admin
from app.admin import forms
from app.storage import demo
from app.storage.memory import MemoryStore

PASSWORD = "секрет-123"
PUBLIC = "https://api.example.kz"


def make_settings(password: str = PASSWORD) -> config.Settings:
    return config.Settings(database_url="", admin_password=password, public_url=PUBLIC, seed_demo=True)


def jpeg(width: int = 2400, height: int = 1800) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (91, 91, 240)).save(out, "JPEG")
    return out.getvalue()


def as_form(values: dict) -> dict:
    """Значения ``forms.fill`` → поля формы, как их отправил бы браузер."""
    data = {}
    for key, value in values.items():
        if isinstance(value, bool):
            if value:
                data[key] = "on"
        elif isinstance(value, list):
            data[key if key != "photos" else "photos.keep"] = value
        else:
            data[key] = value
    return data


NEW_PLACE = {
    "name.ru": "Кофейня «Март»",
    "name.kk": "",
    "category": "coffeeShop",
    "address.ru": "пр. Мангилик Ел, 10",
    "_mapUrl": "https://www.google.com/maps/place/Mart/@51.12,71.44,17z/data=!3d51.1282!4d71.4404",
    "averageCheck": "3500",
    "openingHours.opens": "08:00",
    "openingHours.closes": "22:00",
    "bookingType": "none",
    "goodFor": ["work", "solo"],
    "amenities.wifi.ru": "Бесплатный",
    "amenities.sockets.ru": "Есть",
    "published": "on",
}


class AdminTest(unittest.TestCase):
    def setUp(self):
        admin.FAIL_DELAY_SECONDS = 0
        admin.THROTTLE.reset("testclient")
        self.store = MemoryStore()
        demo.seed(self.store, clock.now())
        self.catalog = services.use(self.store, make_settings())
        site = Starlette(routes=[Mount("/admin", admin.admin_app)])
        self.client = TestClient(site, base_url="https://testserver")

    def tearDown(self):
        services.reset()

    def login(self):
        response = self.client.post(
            "/admin/login?next=/admin/places", data={"password": PASSWORD}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/admin/places")
        return response

    # ---------- Вход ----------

    def test_login_is_required(self):
        response = self.client.get("/admin/places", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/admin/login?next=%2Fadmin%2Fplaces")
        self.assertIn("Вход в админку", self.client.get("/admin/login").text)

    def test_disabled_without_password(self):
        services.use(self.store, make_settings(password=""))
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("ADMIN_PASSWORD", response.text)

    def test_wrong_password_and_throttle(self):
        response = self.client.post("/admin/login", data={"password": "нет"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Неверный пароль", response.text)
        for _ in range(10):
            admin.THROTTLE.fail("testclient")
        response = self.client.post("/admin/login", data={"password": PASSWORD})
        self.assertEqual(response.status_code, 429)

    def test_session_cookie_and_logout(self):
        cookie = self.login().headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("Path=/admin", cookie)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.client.post("/admin/logout")
        self.assertEqual(self.client.get("/admin/", follow_redirects=False).status_code, 303)

    def test_open_redirect_is_ignored(self):
        response = self.client.post(
            "/admin/login?next=https://evil.example/", data={"password": PASSWORD}, follow_redirects=False
        )
        self.assertEqual(response.headers["location"], "/admin/")

    def test_foreign_origin_is_rejected(self):
        self.login()
        response = self.client.post(
            "/admin/demo/delete", headers={"Origin": "https://evil.example"}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(self.store.records("place")), 8)

    # ---------- Списки ----------

    def test_overview_and_lists(self):
        self.login()
        index = self.client.get("/admin/").text
        self.assertIn("Тестовых записей из прототипа: 16", index)
        places = self.client.get("/admin/places?q=garden").text
        self.assertIn("The Garden", places)
        self.assertNotIn("Coffee Lab", places)
        self.assertIn("тест", places)
        events = self.client.get("/admin/events").text
        self.assertIn("Neon Nights", events)
        self.assertEqual(self.client.get("/admin/nope").status_code, 404)
        self.assertEqual(self.client.get("/admin/places/nope").status_code, 404)

    # ---------- Места ----------

    def test_create_place_with_photos(self):
        self.login()
        self.assertIn("Новое место", self.client.get("/admin/places/new").text)
        response = self.client.post(
            "/admin/places/new",
            data=NEW_PLACE,
            files=[("photos.new", ("a.jpg", jpeg(), "image/jpeg")), ("photos.new", ("b.jpg", jpeg(800, 1200), "image/jpeg"))],
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text[:2000])
        self.assertIn("/admin/places?msg=", response.headers["location"])

        record = self.store.get("place", "kofeynya-mart")
        self.assertIsNotNone(record)
        self.assertFalse(record.demo)
        self.assertEqual(record.doc["location"], {"lat": 51.1282, "lng": 71.4404})
        self.assertEqual(len(record.doc["photos"]), 2)

        place = self.catalog.place("kk", "kofeynya-mart")
        self.assertEqual(place["name"], "Кофейня «Март»")
        self.assertEqual(place["distanceKm"], 0.7)
        self.assertTrue(place["photos"][0].startswith(PUBLIC + "/v1/images/"))
        stored = self.store.image(record.doc["photos"][0].split("/")[-1].removesuffix(".jpg"))
        with Image.open(io.BytesIO(stored.data)) as image:
            self.assertEqual(image.size, (1600, 1200))

    def test_validation_keeps_input(self):
        self.login()
        response = self.client.post(
            "/admin/places/new", data={**NEW_PLACE, "averageCheck": "дорого", "_mapUrl": "кафе"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Нужно целое число", response.text)
        self.assertIn("Не нашёл координаты", response.text)
        self.assertIn("Кофейня «Март»", response.text)
        self.assertEqual(len(self.store.records("place")), 8)

    def test_bad_photo_is_reported(self):
        self.login()
        response = self.client.post(
            "/admin/places/new", data=NEW_PLACE, files=[("photos.new", ("a.jpg", b"not an image", "image/jpeg"))]
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Не получилось открыть картинку", response.text)

    def test_edit_hide_and_delete(self):
        self.login()
        page = self.client.get("/admin/places/the_garden").text
        self.assertIn("Тестовая запись из прототипа", page)
        values = forms.fill(forms.PLACE_FIELDS, self.store.get("place", "the_garden").doc)
        data = as_form({**values, "averageCheck": "6500", "photos.remove": values["photos"][-1]})
        response = self.client.post("/admin/places/the_garden", data=data, follow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text[:2000])

        record = self.store.get("place", "the_garden")
        self.assertFalse(record.published)
        self.assertFalse(record.demo)
        self.assertEqual(record.doc["averageCheck"], 6500)
        self.assertEqual(len(record.doc["photos"]), 4)
        self.assertIsNone(self.catalog.place("ru", "the_garden"))

        response = self.client.post("/admin/places/the_garden/delete", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIsNone(self.store.get("place", "the_garden"))
        self.assertEqual(self.client.post("/admin/places/the_garden/delete").status_code, 404)

    def test_delete_demo(self):
        self.login()
        response = self.client.post("/admin/demo/delete")
        self.assertIn("Удалено тестовых записей: 16", response.text)
        self.assertEqual(self.store.records("place"), [])

    # ---------- События ----------

    def test_event_from_venue_and_copy(self):
        self.login()
        data = {
            "title.ru": "Вечер джаза",
            "category": "concert",
            "startsAt": "2030-10-03T19:30",
            "durationMinutes": "90",
            "venuePlaceId": "sky_lounge",
            "tickets.ru": "Партер — 8000\nVIP — 20000",
            "ticketUrl": "https://ticketon.kz/astana",
            "ageLimit": "16",
            "isFeatured": "on",
            "published": "on",
        }
        response = self.client.post(
            "/admin/events/new", data=data,
            files=[("image.new", ("poster.png", jpeg(1000, 1400), "image/png"))], follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text[:2000])
        event = self.catalog.event("ru", "vecher-dzhaza")
        self.assertEqual(event["venueName"], "Sky Lounge")
        self.assertEqual(event["venuePlaceId"], "sky_lounge")
        self.assertEqual(event["priceFrom"], 8000)
        self.assertEqual(event["ageLimit"], 16)
        self.assertTrue(event["image"].startswith(PUBLIC))

        copy = self.client.get("/admin/events/new?from=vecher-dzhaza").text
        self.assertIn("Копия события", copy)
        self.assertIn("Вечер джаза", copy)
        response = self.client.post("/admin/events/new", data={**data, "startsAt": "2030-10-10T19:30"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIsNotNone(self.store.get("event", "vecher-dzhaza-2"))

    def test_event_needs_start(self):
        self.login()
        response = self.client.post("/admin/events/new", data={"title.ru": "Без даты", "category": "concert"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Укажите дату и время", response.text)


if __name__ == "__main__":
    unittest.main()
