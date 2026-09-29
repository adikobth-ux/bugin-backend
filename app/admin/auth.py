"""Вход в админку: один пароль из ``ADMIN_PASSWORD``, подписанная cookie на 30 дней.

Подпись — HMAC от срока действия с ключом из пароля: смена пароля сразу
разлогинивает все устройства. Подбор пароля тормозится: после 10 ошибок за
15 минут с одного адреса вход с него закрывается до конца окна.
"""

import hashlib
import hmac
import threading
import time

COOKIE = "bugin_admin"
SESSION_SECONDS = 30 * 24 * 3600
MAX_FAILURES = 10
WINDOW_SECONDS = 15 * 60


def _key(password: str) -> bytes:
    return hashlib.sha256(b"bugin-admin\0" + password.encode()).digest()


def _sign(password: str, payload: str) -> str:
    return hmac.new(_key(password), payload.encode(), hashlib.sha256).hexdigest()


def make_token(password: str, now: float | None = None) -> str:
    expires = int((now if now is not None else time.time()) + SESSION_SECONDS)
    return f"{expires}.{_sign(password, str(expires))}"


def token_ok(password: str, token: str | None, now: float | None = None) -> bool:
    if not password or not token or "." not in token:
        return False
    expires, signature = token.split(".", 1)
    if not expires.isdigit() or int(expires) < (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(signature, _sign(password, expires))


def password_ok(password: str, attempt: str) -> bool:
    return bool(password) and hmac.compare_digest(attempt.encode(), password.encode())


class Throttle:
    """Счётчик неудачных входов по адресу."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}

    def _recent(self, address: str, now: float) -> list[float]:
        recent = [t for t in self._failures.get(address, []) if now - t < WINDOW_SECONDS]
        self._failures[address] = recent
        return recent

    def blocked(self, address: str, now: float | None = None) -> bool:
        with self._lock:
            return len(self._recent(address, now or time.time())) >= MAX_FAILURES

    def fail(self, address: str, now: float | None = None) -> None:
        moment = now or time.time()
        with self._lock:
            self._recent(address, moment).append(moment)

    def reset(self, address: str) -> None:
        with self._lock:
            self._failures.pop(address, None)
