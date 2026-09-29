"""Расстояния и координаты.

Пока приложение не присылает своё местоположение, «рядом» считается от центра
Астаны (Байтерек). Координаты места админка берёт из ссылки 2ГИС, Google Maps или
Яндекс Карт — вводить цифры вручную не нужно.
"""

import math
import re
from urllib.parse import unquote, urlparse

from app.domain.texts import dart_round

# Байтерек — от него считаем «рядом», пока нет геолокации.
ASTANA_CENTER = (51.1282, 71.4304)

_EARTH_KM = 6371.0


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Расстояние по прямой (формула гаверсинусов), км."""
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * _EARTH_KM * math.asin(math.sqrt(h))


def rounded_km(km: float) -> float:
    """До десятых: так расстояние показывает приложение."""
    return round(km + 1e-9, 1)


def taxi_minutes(km: float) -> int:
    """Грубая оценка поездки по городу: подача и 2,6 минуты на километр."""
    return max(3, dart_round(2 + km * 2.6))


def point(location: object) -> tuple[float, float] | None:
    """``{"lat": …, "lng": …}`` → (lat, lng); что-то другое → None."""
    if not isinstance(location, dict):
        return None
    lat, lng = location.get("lat"), location.get("lng")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return (float(lat), float(lng))
    return None


# ---------- Координаты из ссылки на карту ----------

_NUM = r"(-?\d{1,3}(?:\.\d+)?)"
_GOOGLE_PLACE = re.compile(r"!3d" + _NUM + r"!4d" + _NUM)
_GOOGLE_AT = re.compile(r"@" + _NUM + r"," + _NUM)
_GOOGLE_QUERY = re.compile(r"[?&](?:q|query|ll|destination|center)=(?:loc:)?" + _NUM + r",\s*" + _NUM)
_TWO_GIS_M = re.compile(r"[?&]m=" + _NUM + r"," + _NUM)
_TWO_GIS_PATH = re.compile(r"/" + _NUM + r"," + _NUM + r"(?:[/?#]|$)")
_YANDEX = re.compile(r"(?:[?&](?:ll|pt|rtext)|whatshere\[point\])=~?" + _NUM + r"," + _NUM)
_PLAIN = re.compile(r"^\s*" + _NUM + r"\s*[,;\s]\s*" + _NUM + r"\s*$")

# Короткие ссылки «Поделиться»: координаты появляются только после перехода.
SHORT_LINK_HOSTS = ("go.2gis.com", "maps.app.goo.gl", "goo.gl")


def _valid(lat: float, lng: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lng <= 180 and (lat, lng) != (0.0, 0.0)


def _kz_order(a: float, b: float) -> tuple[float, float]:
    """Порядок для голых цифр: в Казахстане широта 40–56, долгота 46–88."""
    if 40 <= b <= 56 and 46 <= a <= 88 and not (40 <= a <= 56 and 46 <= b <= 88):
        return (b, a)
    return (a, b)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_short_link(url: str) -> bool:
    host = _host(url.strip())
    return host in SHORT_LINK_HOSTS or (
        "yandex" in host and "/maps/-/" in urlparse(url.strip()).path
    )


def is_map_host(host: str) -> bool:
    """Хосты карт, по чьим редиректам можно ходить с сервера."""
    host = host.lower()
    return host in SHORT_LINK_HOSTS or any(
        host == name or host.endswith("." + name)
        for name in ("2gis.kz", "2gis.ru", "2gis.com", "google.com", "google.kz", "yandex.kz", "yandex.ru", "yandex.com")  # noqa: E501
    )


def parse_map_link(text: str) -> tuple[float, float] | None:
    """(широта, долгота) из ссылки на карту или из «51.12, 71.43»; не нашли → None."""
    raw = (text or "").strip()
    if not raw:
        return None
    plain = _PLAIN.match(raw)
    if plain:
        lat, lng = _kz_order(float(plain.group(1)), float(plain.group(2)))
        return (lat, lng) if _valid(lat, lng) else None

    s = unquote(unquote(raw))
    host = _host(s)
    found: tuple[float, float] | None = None
    if "2gis" in host:
        m = _TWO_GIS_M.search(s) or _TWO_GIS_PATH.search(s)
        if m:
            found = (float(m.group(2)), float(m.group(1)))  # в 2ГИС сначала долгота
    elif "yandex" in host:
        m = _YANDEX.search(s)
        if m:
            found = (float(m.group(2)), float(m.group(1)))  # в Яндексе тоже
    elif "google" in host or "goo.gl" in host:
        m = _GOOGLE_PLACE.search(s) or _GOOGLE_QUERY.search(s) or _GOOGLE_AT.search(s)
        if m:
            found = (float(m.group(1)), float(m.group(2)))
    if found is not None and _valid(*found):
        return found
    return None
