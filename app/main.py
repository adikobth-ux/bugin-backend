"""Сервер Bugin: приложение FastAPI.

Запуск: ``uvicorn app.main:app --reload``, документация — ``/docs``, админка — ``/admin``.
Контракт — ``docs/api.md``. Настройки — переменные окружения (``app/config.py``).
"""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import services
from app.admin.app import admin_app
from app.api import evening, events, places, search
from app.api.schemas import ERROR_RESPONSES, Health


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Подключаемся к базе сразу: неверный DATABASE_URL виден в логе деплоя,
    # а Render оставляет работать прошлую версию.
    await run_in_threadpool(services.startup)
    yield


app = FastAPI(
    title="Bugin API",
    version="0.2.0",
    description=(
        "Сервер приложения Bugin «Чем заняться сегодня?»: места и события Астаны из "
        "каталога (админка — /admin), AI-поиск и «Собрать мне вечер». Язык ответа — "
        "заголовок Accept-Language (kk → казахский, иначе русский)."
    ),
    lifespan=lifespan,
)

# Веб-версия приложения живёт на другом домене (github.io); cookies не используются.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=False,
)

for module in (places, events, search, evening):
    app.include_router(module.router, prefix="/v1")

app.mount("/admin", admin_app)


# ---------- Ошибки в формате контракта ----------

_DEFAULT_MESSAGES = {
    404: "Такого адреса нет",
    405: "Этот метод здесь не поддерживается",
}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _code_for(status: int) -> str:
    if status == 404:
        return "not_found"
    if status >= 500:
        return "internal"
    return "bad_request"


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    # Для чужих ошибок Starlette («Not Found») — понятный текст по-русски.
    if exc.status_code in _DEFAULT_MESSAGES and message in ("Not Found", "Method Not Allowed"):
        message = _DEFAULT_MESSAGES[exc.status_code]
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(_code_for(exc.status_code), message),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for error in exc.errors()[:5]:
        where = ".".join(str(part) for part in error.get("loc", ()))
        what = error.get("msg", "")
        parts.append(f"{where}: {what}" if where else what)
    message = "Некорректный запрос — " + "; ".join(parts)
    return JSONResponse(status_code=422, content=error_body("bad_request", message))


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception) -> JSONResponse:
    # Подробности — в логе сервера (Starlette пробрасывает исключение дальше).
    return JSONResponse(status_code=500, content=error_body("internal", "Внутренняя ошибка сервера"))


# ---------- Служебное ----------


@app.get("/health", response_model=Health, tags=["Служебное"], summary="Проверка доступности")
def health() -> dict:
    """Без запроса к базе: Render проверяет часто, а Neon должен успевать засыпать."""
    return {"status": "ok", "storage": services.store().name}


_IMAGE_NAME = re.compile(r"^([0-9a-f]{8,32})\.jpg$")


@app.get(
    "/v1/images/{name}",
    tags=["Служебное"],
    summary="Фото из админки",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}, **ERROR_RESPONSES},
)
def image(name: str) -> Response:
    """JPEG из каталога. Ссылки не меняются, поэтому кэшируются надолго."""
    match = _IMAGE_NAME.match(name)
    stored = services.store().image(match.group(1)) if match else None
    if stored is None:
        raise StarletteHTTPException(status_code=404, detail="Фото не найдено")
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
