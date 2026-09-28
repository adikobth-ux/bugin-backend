"""Тестовый сервер Bugin (этап 0): приложение FastAPI.

Запуск: ``uvicorn app.main:app --reload``, документация — ``/docs``.
Контракт — ``docs/api.md``.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import evening, events, places, search
from app.api.schemas import Health

app = FastAPI(
    title="Bugin API",
    version="0.1.0",
    description=(
        "Тестовый сервер приложения Bugin «Чем заняться сегодня?» (этап 0): "
        "данные прототипа, без входа и личных данных. Язык ответа — заголовок "
        "Accept-Language (kk → казахский, иначе русский)."
    ),
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
    return {"status": "ok"}
