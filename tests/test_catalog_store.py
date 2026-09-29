"""Каталог из хранилища: двуязычные документы, координаты, формы админки.

Без внешних зависимостей: ``python -m unittest discover -s tests -t .``.
"""

import unittest
from datetime import datetime

from app.admin import forms, photos
from app.domain import geo, i18n
from app.domain.catalog import Catalog, price_level
from app.domain.planner import WORK_DAY_ID, EveningPlanner, default_request
from app.storage import demo
from app.storage.memory import MemoryStore

NOW = datetime(2026, 9, 29, 12, 0)

# Настоящее место, как его сохраняет админка: координаты вместо расстояния,
# казахский заполнен не везде.
COFFEE = {
    "name": "Март",
    "category": "coffeeShop",
    "subtitle": {"ru": "Кофе у парка", "kk": "Саябақ жанындағы кофе"},
    "pitch": {"ru": "Тихо и розетки у каждого стола", "kk": ""},
    "address": {"ru": "пр. Мангилик Ел, 10", "kk": "Мәңгілік Ел даңғылы, 10"},
    "averageCheck": 3500,
    "openingHours": {"opensAt": 480, "closesAt": 1320},
    "photos": ["/v1/images/0123456789abcdef.jpg"],
    "tags": {"ru": ["Кофе", "Десерты"], "kk": ["Кофе"]},
    "amenities": [
        {"type": "wifi", "value": {"ru": "Бесплатный", "kk": "Тегін"}},
        {"type": "sockets", "value": "Есть"},
    ],
    "goodFor": ["work", "solo"],
    "vibes": ["calm"],
    "location": {"lat": 51.1282, "lng": 71.4404},
    "_mapUrl": "https://2gis.kz/astana/geo/1/71.4404,51.1282",
}

DINNER = {
    "name": "Қазан",
    "category": "restaurant",
    "address": "ул. Кенесары, 1",
    "averageCheck": 9000,
    "rating": 4.9,
    "vibes": ["beautiful"],
    "goodFor": ["date"],
    "location": {"lat": 51.1682, "lng": 71.4304},
}


class I18nTest(unittest.TestCase):
    def test_localize_picks_language_and_falls_back_to_russian(self):
        kk = i18n.localize(COFFEE, "kk")
        self.assertEqual(kk["subtitle"], "Саябақ жанындағы кофе")
        self.assertEqual(kk["pitch"], "Тихо и розетки у каждого стола")
        self.assertEqual(kk["tags"], ["Кофе"])
        self.assertEqual(kk["amenities"][0]["value"], "Тегін")
        self.assertEqual(i18n.localize(COFFEE, "ru")["tags"], ["Кофе", "Десерты"])
        self.assertEqual(i18n.localize(COFFEE, "kk")["name"], "Март")

    def test_merge_and_pair(self):
        merged = i18n.merge({"a": "да", "n": 1, "l": ["x", "y"]}, {"a": "иә", "n": 1, "l": ["z"]})
        self.assertEqual(merged, {"a": {"ru": "да", "kk": "иә"}, "n": 1, "l": {"ru": ["x", "y"], "kk": ["z"]}})
        self.assertEqual(i18n.pair("Кофе", ""), "Кофе")
        self.assertEqual(i18n.pair("Кофе", "Кофе"), "Кофе")
        self.assertEqual(i18n.pair([], []), [])


class GeoTest(unittest.TestCase):
    def test_links_of_map_services(self):
        cases = {
            "https://2gis.kz/astana/firm/70000001?m=71.430411%2C51.128207%2F17": (51.128207, 71.430411),
            "https://2gis.kz/astana/geo/9570784863358987/71.4304,51.1282": (51.1282, 71.4304),
            "https://www.google.com/maps/place/Bayterek/@51.1283,71.4297,17z/data=!3m1!4b1!4m6!3m5!1s0x0:0x0!8m2!3d51.128207!4d71.430411": (51.128207, 71.430411),  # noqa: E501
            "https://maps.google.com/?q=51.1282,71.4304": (51.1282, 71.4304),
            "https://yandex.kz/maps/163/astana/?ll=71.430411%2C51.128207&z=17": (51.128207, 71.430411),
            "51.128207, 71.430411": (51.128207, 71.430411),
            "71.430411 51.128207": (51.128207, 71.430411),
        }
        for link, expected in cases.items():
            self.assertEqual(geo.parse_map_link(link), expected, link)
        self.assertIsNone(geo.parse_map_link("https://2gis.kz/astana/firm/70000001"))
        self.assertIsNone(geo.parse_map_link("кафе на Абая"))

    def test_short_links_and_hosts(self):
        self.assertTrue(geo.is_short_link("https://go.2gis.com/ab12c"))
        self.assertTrue(geo.is_short_link("https://maps.app.goo.gl/XyZ"))
        self.assertTrue(geo.is_short_link("https://yandex.kz/maps/-/CDabc"))
        self.assertFalse(geo.is_short_link("https://2gis.kz/astana"))
        self.assertTrue(geo.is_map_host("www.google.com"))
        self.assertFalse(geo.is_map_host("google.com.evil.example"))
        self.assertFalse(geo.is_map_host("169.254.169.254"))

    def test_distance_and_taxi(self):
        km = geo.distance_km(geo.ASTANA_CENTER, (51.1682, 71.4304))
        self.assertAlmostEqual(km, 4.45, places=1)
        self.assertEqual(geo.rounded_km(km), 4.4)
        self.assertEqual(geo.taxi_minutes(0.2), 3)
        self.assertEqual(geo.taxi_minutes(4.4), 13)


class CatalogFromStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.save("place", "mart", COFFEE, published=True)
        self.store.save("place", "kazan", DINNER, published=True)
        self.store.save("place", "hidden", {**DINNER, "name": "Черновик"}, published=False)
        self.catalog = Catalog(self.store, public_url="https://bugin-api.onrender.com")

    def test_computed_fields(self):
        mart = self.catalog.place("ru", "mart")
        self.assertEqual(mart["id"], "mart")
        self.assertEqual(mart["distanceKm"], 0.7)
        self.assertEqual(mart["taxiMinutes"], 4)
        self.assertEqual(mart["priceLevel"], 2)
        self.assertEqual(mart["photos"], ["https://bugin-api.onrender.com/v1/images/0123456789abcdef.jpg"])
        self.assertEqual(mart["bookingType"], "none")
        self.assertEqual(mart["reviews"], [])
        self.assertNotIn("_mapUrl", mart)
        self.assertEqual(price_level(0), 1)
        self.assertEqual(price_level(20000), 4)

    def test_hidden_records_are_not_shown(self):
        self.assertIsNone(self.catalog.place("ru", "hidden"))
        self.assertEqual([p["id"] for p in self.catalog.nearby("ru")], ["mart", "kazan"])

    def test_changes_are_visible_at_once(self):
        self.assertEqual(self.catalog.place("kk", "kazan")["averageCheck"], 9000)
        self.store.save("place", "kazan", {**DINNER, "averageCheck": 7000}, published=True)
        self.assertEqual(self.catalog.place("kk", "kazan")["averageCheck"], 7000)
        self.store.delete("place", "kazan")
        self.assertIsNone(self.catalog.place("ru", "kazan"))

    def test_event_defaults_price_and_missing_venue(self):
        self.store.save(
            "event", "jazz",
            {
                "title": "Джаз",
                "category": "concert",
                "startsAt": "2026-09-29T20:00:00",
                "tickets": [{"name": "Партер", "price": 8000}, {"name": "Балкон", "price": 5000}],
                "venuePlaceId": "hidden",
                "location": {"lat": 51.1282, "lng": 71.4404},
            },
            published=True,
        )
        event = self.catalog.event("ru", "jazz")
        self.assertEqual(event["priceFrom"], 5000)
        self.assertIsNone(event["venuePlaceId"])
        self.assertEqual(event["image"], "")
        self.assertEqual(event["durationMinutes"], 120)
        self.assertEqual([e["id"] for e in self.catalog.events_for_day("ru", NOW, "today")], ["jazz"])

    def test_planner_on_real_places(self):
        planner = EveningPlanner("ru", self.catalog.places("ru"))
        self.assertEqual(planner.featured(NOW)["id"], WORK_DAY_ID)
        plan = planner.plan(default_request(budget=20000))
        self.assertEqual([s["placeId"] for s in plan["stops"]], ["mart", "kazan"])
        self.assertEqual(plan["stops"][1]["kind"], "dinner_view")
        self.assertEqual(plan["legs"][0]["mode"], "taxi")

    def test_planner_without_suitable_places(self):
        empty = EveningPlanner("ru", [])
        self.assertEqual(empty.featured(NOW)["stops"], [])
        self.assertEqual(empty.library(), [])
        only_dinner = EveningPlanner("ru", [self.catalog.place("ru", "kazan")])
        self.assertEqual(only_dinner.featured(NOW)["id"], "calm_evening_pair")


class DemoSeedTest(unittest.TestCase):
    def test_seeded_once_and_removable(self):
        store = MemoryStore()
        self.assertTrue(demo.seed(store, NOW))
        self.assertEqual(len(store.records("place")), 8)
        self.assertEqual(store.delete_demo(), 16)
        self.assertFalse(demo.seed(store, NOW))
        self.assertEqual(store.records("event"), [])


class FormsTest(unittest.TestCase):
    class Form(dict):
        def getlist(self, key):
            value = self.get(key)
            if value is None:
                return []
            return value if isinstance(value, list) else [value]

    def form(self, **values):
        return self.Form({key.replace("__", "."): value for key, value in values.items()})

    def test_place_round_trip(self):
        values = forms.fill(forms.PLACE_FIELDS, COFFEE)
        self.assertEqual(values["subtitle.kk"], "Саябақ жанындағы кофе")
        self.assertEqual(values["tags.ru"], "Кофе, Десерты")
        self.assertEqual(values["openingHours.opens"], "08:00")
        self.assertEqual(values["amenities.sockets.ru"], "Есть")
        form = self.Form(values)
        form["photos.keep"] = list(COFFEE["photos"])
        parsed = forms.parse(forms.PLACE_FIELDS, form, forms.Context(previous=COFFEE))
        self.assertTrue(parsed.ok, parsed.errors)
        for key in ("name", "subtitle", "pitch", "address", "tags", "amenities", "openingHours", "location", "photos"):
            for lang in ("ru", "kk"):
                # Пара с пустым казахским сохраняется просто строкой — показ тот же.
                self.assertEqual(
                    i18n.localize(parsed.doc[key], lang), i18n.localize(COFFEE[key], lang), key
                )

    def test_new_place_from_map_link_and_errors(self):
        form = self.form(
            name__ru="Бар «Ночь»",
            category="restaurant",
            address__ru="ул. Сыганак, 5",
            _mapUrl="https://2gis.kz/astana/firm/1?m=71.41%2C51.09%2F16",
            averageCheck="12 000",
            openingHours__opens="18:00",
            openingHours__closes="02:00",
            bookingType="table",
            goodFor=["friends", "nope"],
        )
        parsed = forms.parse(forms.PLACE_FIELDS, form, forms.Context())
        self.assertTrue(parsed.ok, parsed.errors)
        self.assertEqual(parsed.doc["location"], {"lat": 51.09, "lng": 71.41})
        self.assertEqual(parsed.doc["averageCheck"], 12000)
        self.assertEqual(parsed.doc["openingHours"], {"opensAt": 1080, "closesAt": 1560})
        self.assertEqual(parsed.doc["goodFor"], ["friends"])

        bad = self.form(name__ru="", category="spa", _mapUrl="https://2gis.kz/astana", averageCheck="много")
        errors = forms.parse(forms.PLACE_FIELDS, bad, forms.Context()).errors
        self.assertEqual(set(errors), {"name", "category", "address", "location", "averageCheck", "openingHours"})

    def test_event_tickets_venue_and_photos(self):
        venue = {**DINNER, "id": "kazan"}
        form = self.form(
            title__ru="Вечер романса",
            category="concert",
            startsAt="2026-10-03T19:30",
            durationMinutes="90",
            venuePlaceId="kazan",
            tickets__ru="Партер — 12 000 ₸\nVIP-зона: 30000",
            tickets__kk="Партер",
            ticketUrl="ticketon.kz",
        )
        parsed = forms.parse(forms.EVENT_FIELDS, form, forms.Context(places={"kazan": venue}))
        self.assertEqual(parsed.errors, {"ticketUrl": "Ссылка должна начинаться с https://"})
        doc = parsed.doc
        self.assertEqual(doc["startsAt"], "2026-10-03T19:30:00")
        self.assertEqual(doc["tickets"], [{"name": "Партер", "price": 12000}, {"name": "VIP-зона", "price": 30000}])
        self.assertEqual(doc["priceFrom"], 12000)
        self.assertEqual(doc["venueName"], "Қазан")
        self.assertEqual(doc["location"], DINNER["location"])
        self.assertEqual(doc["ageLimit"], 0)

        previous = {"photos": ["/v1/images/aaaa0000aaaa0000.jpg", "/v1/images/bbbb0000bbbb0000.jpg"]}
        form = self.form(**{"photos__keep": previous["photos"], "photos__remove": previous["photos"][0]})
        ctx = forms.Context(previous=previous, uploads={"photos": ["/v1/images/cccc0000cccc0000.jpg"]})
        parsed = forms.parse([f for f in forms.PLACE_FIELDS if f.key == "photos"], form, ctx)
        self.assertEqual(parsed.doc["photos"], ["/v1/images/bbbb0000bbbb0000.jpg", "/v1/images/cccc0000cccc0000.jpg"])
        self.assertEqual(parsed.removed_images, ["/v1/images/aaaa0000aaaa0000.jpg"])

    def test_ids(self):
        self.assertEqual(forms.slug("Кофейня «Март»"), "kofeynya-mart")
        self.assertEqual(forms.slug("Қазан & Co"), "qazan-co")
        taken = {"mart"}
        self.assertEqual(forms.new_id("Март", taken.__contains__, "place"), "mart-2")
        self.assertEqual(forms.new_id("!!!", taken.__contains__, "place"), "place")

    def test_image_ids(self):
        self.assertEqual(photos.image_id("https://x.kz/v1/images/0123abcd0123abcd.jpg"), "0123abcd0123abcd")
        self.assertIsNone(photos.image_id("assets/images/place_the_garden.jpg"))
        self.assertIsNone(photos.image_id("/v1/images/../../etc.jpg"))


if __name__ == "__main__":
    unittest.main()
