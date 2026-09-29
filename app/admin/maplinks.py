"""Короткие ссылки «Поделиться» (go.2gis.com, maps.app.goo.gl, yandex.kz/maps/-/…).

Координат в них нет — они появляются в адресе после перенаправления. Сервер
проходит перенаправления сам, но только по хостам карт (``geo.is_map_host``),
чтобы админка не стала прокси в произвольные адреса.
"""

import logging
from urllib.parse import urljoin, urlparse

import httpx

from app.domain import geo

log = logging.getLogger(__name__)

MAX_HOPS = 6
TIMEOUT = 8.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (Bugin admin; +https://github.com/adikobth-ux/bugin)"}


def resolve(url: str) -> tuple[float, float] | None:
    """Координаты из короткой ссылки или None. Сетевые ошибки не пробрасываются."""
    current = url.strip()
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=False, headers=_HEADERS) as client:
            for _ in range(MAX_HOPS):
                if not geo.is_map_host(urlparse(current).hostname or ""):
                    return None
                found = geo.parse_map_link(current)
                if found is not None:
                    return found
                response = client.get(current)
                location = response.headers.get("location")
                if not response.is_redirect or not location:
                    return geo.parse_map_link(str(response.url))
                current = urljoin(current, location)
    except httpx.HTTPError as error:
        log.warning("Не удалось раскрыть ссылку на карту %s: %s", url, error)
    return None
