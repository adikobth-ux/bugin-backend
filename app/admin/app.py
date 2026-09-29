"""Админка Bugin (``/admin``): места и события Астаны.

Обычные HTML-формы без JS-фреймворков — удобно с телефона и нечему ломаться.
Приложение Starlette, подключается в FastAPI через ``mount`` и не попадает в ``/docs``.
Работа с базой идёт в пуле потоков (``run_in_threadpool``), чтобы не держать
event loop.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from app import clock, services
from app.admin import auth, forms, maplinks, photos
from app.domain import geo, i18n, texts
from app.domain.catalog import IMAGE_PATH

log = logging.getLogger(__name__)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
THROTTLE = auth.Throttle()

MAX_FILES = 12
FAIL_DELAY_SECONDS = 1.0  # пауза после неверного пароля
MAX_UPLOAD_TOTAL = 80 * 1024 * 1024


@dataclass(frozen=True)
class Kind:
    code: str  # вид в хранилище
    path: str  # часть адреса
    fields: list[forms.Field]
    title_key: str
    many: str
    one: str
    new_label: str
    categories: dict[str, str]


KINDS = {
    "places": Kind(
        "place", "places", forms.PLACE_FIELDS, "name", "Места", "место", "Новое место",
        dict(forms.PLACE_CATEGORIES),
    ),
    "events": Kind(
        "event", "events", forms.EVENT_FIELDS, "title", "События", "событие", "Новое событие",
        dict(forms.EVENT_CATEGORIES),
    ),
}


# ---------- Общее ----------


def _base(request: Request) -> str:
    return request.scope.get("root_path", "").rstrip("/")


def _thumb(url: object) -> str | None:
    """Ссылка для превью в админке; фото из ассетов приложения на сервере нет."""
    if not isinstance(url, str) or not url:
        return None
    if url.startswith((IMAGE_PATH, "https://", "http://")):
        return url
    return None


TEMPLATES.env.globals["thumb"] = _thumb
TEMPLATES.env.filters["tenge"] = lambda value: texts.tenge(int(value or 0))
TEMPLATES.env.filters["t"] = lambda value, lang="ru": i18n.text(value, lang)


def render(request: Request, name: str, context: dict | None = None, status: int = 200) -> Response:
    ctx = {
        "base": _base(request),
        "storage": services.store().name if services.settings().admin_password else "",
        "logged_in": _logged_in(request),
    }
    ctx.update(context or {})
    return TEMPLATES.TemplateResponse(request, name, ctx, status_code=status)


def _password() -> str:
    return services.settings().admin_password


def _logged_in(request: Request) -> bool:
    return auth.token_ok(_password(), request.cookies.get(auth.COOKIE))


def _same_origin(request: Request) -> bool:
    """Формы — только со своих страниц (вдобавок к SameSite=Lax у cookie)."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    return urlparse(origin).netloc == request.url.netloc


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def guarded(handler):
    async def wrapper(request: Request) -> Response:
        if not _password():
            return render(request, "disabled.html", status=503)
        if not _logged_in(request):
            query = urlencode({"next": request.url.path})
            return RedirectResponse(f"{_base(request)}/login?{query}", status_code=303)
        if request.method == "POST" and not _same_origin(request):
            return render(request, "message.html", {"title": "Запрос с чужой страницы отклонён"}, 403)
        return await handler(request)

    return wrapper


def _kind(request: Request) -> Kind:
    kind = KINDS.get(request.path_params.get("kind", ""))
    if kind is None:
        raise HTTPException(404)
    return kind


def _event_end(doc: dict) -> datetime | None:
    try:
        start = datetime.fromisoformat(doc.get("startsAt", ""))
    except ValueError:
        return None
    return start + timedelta(minutes=int(doc.get("durationMinutes") or 0))


# ---------- Вход ----------


async def login(request: Request) -> Response:
    if not _password():
        return render(request, "disabled.html", status=503)
    base = _base(request)
    target = request.query_params.get("next", "")
    if not target.startswith(base + "/") or target.startswith("//"):
        target = base + "/"
    if request.method == "GET":
        return render(request, "login.html", {"next": target})

    address = _client(request)
    if THROTTLE.blocked(address):
        return render(
            request, "login.html",
            {"next": target, "error": "Слишком много попыток. Подождите 15 минут."}, 429,
        )
    form = await request.form()
    attempt = form.get("password")
    if not isinstance(attempt, str) or not auth.password_ok(_password(), attempt):
        THROTTLE.fail(address)
        await asyncio.sleep(FAIL_DELAY_SECONDS)
        return render(request, "login.html", {"next": target, "error": "Неверный пароль"}, 401)
    THROTTLE.reset(address)
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        auth.COOKIE,
        auth.make_token(_password()),
        max_age=auth.SESSION_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path=base or "/",
    )
    return response


async def logout(request: Request) -> Response:
    response = RedirectResponse(f"{_base(request)}/login", status_code=303)
    response.delete_cookie(auth.COOKIE, path=_base(request) or "/")
    return response


# ---------- Главная ----------


def _overview() -> dict:
    store = services.store()
    places = store.records("place")
    events = store.records("event")
    now = clock.now()
    upcoming = [e for e in events if (_event_end(e.doc) or now) >= now]
    return {
        "places": len(places),
        "places_hidden": sum(1 for r in places if not r.published),
        "events_upcoming": len(upcoming),
        "events_past": len(events) - len(upcoming),
        "demo": sum(1 for r in places + events if r.demo),
    }


@guarded
async def index(request: Request) -> Response:
    overview = await run_in_threadpool(_overview)
    return render(request, "index.html", {"o": overview, "msg": request.query_params.get("msg")})


@guarded
async def delete_demo(request: Request) -> Response:
    count = await run_in_threadpool(services.store().delete_demo)
    return RedirectResponse(f"{_base(request)}/?{urlencode({'msg': f'Удалено тестовых записей: {count}'})}", 303)


# ---------- Списки ----------


def _rows(kind: Kind, query: str) -> list[dict]:
    now = clock.now()
    rows = []
    for record in services.store().records(kind.code):
        doc = record.doc
        title = i18n.text(doc.get(kind.title_key)) or record.id
        category = kind.categories.get(doc.get("category", ""), "")
        if kind.code == "place":
            photo = next(iter(doc.get("photos") or []), "")
            details = " · ".join(x for x in (category, i18n.text(doc.get("address"))) if x)
            past, sort_key = False, (0, title.lower())
        else:
            photo = doc.get("image") or ""
            end = _event_end(doc)
            past = end is not None and end < now
            when = doc.get("startsAt", "")[:16].replace("T", " ")
            details = " · ".join(x for x in (when, category, i18n.text(doc.get("venueName"))) if x)
            start = doc.get("startsAt", "")
            # Сначала предстоящие по возрастанию, потом прошедшие — свежие сверху.
            sort_key = (1, "".join(chr(0x10FFFF - ord(c)) for c in start)) if past else (0, start)
        haystack = f"{title} {details} {i18n.text(doc.get(kind.title_key), 'kk')}".lower()
        if query and query.lower() not in haystack:
            continue
        rows.append(
            {
                "id": record.id,
                "title": title,
                "details": details,
                "photo": photo,
                "demo": record.demo,
                "published": record.published,
                "past": past,
                "sort": sort_key,
            }
        )
    rows.sort(key=lambda row: row["sort"])
    return rows


@guarded
async def list_items(request: Request) -> Response:
    kind = _kind(request)
    query = request.query_params.get("q", "").strip()
    rows = await run_in_threadpool(_rows, kind, query)
    return render(
        request, "list.html",
        {"kind": kind, "rows": rows, "q": query, "msg": request.query_params.get("msg")},
    )


# ---------- Форма ----------


def _place_options() -> tuple[list[tuple[str, str]], dict[str, dict]]:
    records = services.store().records("place")
    docs = {r.id: r.doc for r in records}
    options = sorted(((r.id, i18n.text(r.doc.get("name")) or r.id) for r in records), key=lambda o: o[1].lower())
    return options, docs


def _form_context(kind: Kind, item_id: str | None, doc: dict, values: dict, errors: dict,
                  published: bool, demo: bool) -> dict:
    place_options = _place_options()[0] if kind.code == "event" else []
    return {
        "kind": kind,
        "item_id": item_id,
        "title": i18n.text(doc.get(kind.title_key)) if item_id else kind.new_label,
        "sections": forms.sections(kind.fields),
        "v": values,
        "errors": errors,
        "published": published,
        "demo": demo,
        "place_options": place_options,
        "amenities": forms.AMENITIES,
    }


@guarded
async def edit(request: Request) -> Response:
    kind = _kind(request)
    item_id = request.path_params.get("item_id")
    store = services.store()
    doc: dict = {}
    published, demo = True, False
    if item_id is not None:
        record = await run_in_threadpool(store.get, kind.code, item_id)
        if record is None:
            raise HTTPException(404)
        doc, published, demo = record.doc, record.published, record.demo
    elif source_id := request.query_params.get("from"):
        # «Копировать событие»: всё, кроме даты — её обычно и меняют.
        source = await run_in_threadpool(store.get, kind.code, source_id)
        if source is not None:
            doc = {k: v for k, v in source.doc.items() if k not in ("id", "startsAt")}
    values = forms.fill(kind.fields, doc)
    context = _form_context(kind, item_id, doc, values, {}, published, demo)
    context["copy"] = item_id is None and bool(doc)
    return render(request, "form.html", context)


async def _read_uploads(form, names: list[str]) -> tuple[dict[str, list[bytes]], str | None]:
    uploads: dict[str, list[bytes]] = {}
    total, count = 0, 0
    for name in names:
        for item in form.getlist(f"{name}.new"):
            if not isinstance(item, UploadFile) or not item.filename:
                continue
            data = await item.read()
            if not data:
                continue
            count += 1
            total += len(data)
            if count > MAX_FILES:
                return {}, f"За раз — не больше {MAX_FILES} фото"
            if total > MAX_UPLOAD_TOTAL:
                return {}, "Слишком много мегабайт за раз — загрузите фото в два захода"
            uploads.setdefault(name, []).append(data)
    return uploads, None


def _save_photos(uploads: dict[str, list[bytes]]) -> dict[str, list[str]]:
    store = services.store()
    saved: dict[str, list[str]] = {}
    try:
        for name, files in uploads.items():
            for data in files:
                saved.setdefault(name, []).append(photos.save(store, data))
    except photos.PhotoError:
        photos.delete_unused(store, [url for urls in saved.values() for url in urls])
        raise
    return saved


@guarded
async def save(request: Request) -> Response:
    kind = _kind(request)
    item_id = request.path_params.get("item_id")
    store = services.store()
    record = None
    if item_id is not None:
        record = await run_in_threadpool(store.get, kind.code, item_id)
        if record is None:
            raise HTTPException(404)
    previous = record.doc if record else {}
    upload_fields = [f.key for f in kind.fields if f.kind in ("photos", "image")]

    async with request.form(max_files=MAX_FILES * 2, max_fields=600) as form:
        uploads, upload_error = await _read_uploads(form, upload_fields)
        published = form.get("published") in ("on", "1", "true")
        places = (await run_in_threadpool(_place_options))[1] if kind.code == "event" else {}

        link = form.get("_mapUrl")
        resolved = None
        if isinstance(link, str) and link.strip() != previous.get("_mapUrl", "") and geo.is_short_link(link):
            resolved = await run_in_threadpool(maplinks.resolve, link)

        ctx = forms.Context(previous=previous, resolved_geo=resolved, places=places)
        parsed = forms.parse(kind.fields, form, ctx)
        if upload_error:
            parsed.errors[upload_fields[0]] = upload_error
        if parsed.ok and uploads:
            try:
                ctx.uploads = await run_in_threadpool(_save_photos, uploads)
            except photos.PhotoError as error:
                parsed.errors[upload_fields[0]] = str(error)
            else:
                parsed = forms.parse(kind.fields, form, ctx)

        if not parsed.ok:
            values = forms.fill(kind.fields, {**parsed.doc, "_mapUrl": parsed.doc.get("_mapUrl", "")})
            # Введённое пользователем показываем как есть, даже если оно с ошибкой.
            for key in form.keys():
                raw = form.get(key)
                if isinstance(raw, str) and not key.startswith("photos.") and key in values:
                    values[key] = raw
            context = _form_context(kind, item_id, previous, values, parsed.errors, published, bool(record and record.demo))
            if uploads:
                context["uploads_lost"] = True
            return render(request, "form.html", context, status=422)

    def commit() -> str:
        new_id = item_id or forms.new_id(
            i18n.text(parsed.doc.get(kind.title_key)),
            lambda candidate: store.get(kind.code, candidate) is not None,
            kind.code,
        )
        # Правленая тестовая запись становится обычной: её уже не удалит «Удалить тестовые».
        store.save(kind.code, new_id, parsed.doc, published=published, demo=False)
        photos.delete_unused(store, parsed.removed_images)
        return new_id

    saved_id = await run_in_threadpool(commit)
    title = i18n.text(parsed.doc.get(kind.title_key)) or saved_id
    query = urlencode({"msg": f"Сохранено: {title}" + ("" if published else " (скрыто)")})
    return RedirectResponse(f"{_base(request)}/{kind.path}?{query}", status_code=303)


@guarded
async def delete(request: Request) -> Response:
    kind = _kind(request)
    item_id = request.path_params["item_id"]
    store = services.store()

    def remove() -> str | None:
        record = store.get(kind.code, item_id)
        if record is None:
            return None
        store.delete(kind.code, item_id)
        urls = list(record.doc.get("photos") or []) + [record.doc.get("image") or ""]
        photos.delete_unused(store, [u for u in urls if isinstance(u, str)])
        return i18n.text(record.doc.get(kind.title_key)) or item_id

    title = await run_in_threadpool(remove)
    if title is None:
        raise HTTPException(404)
    query = urlencode({"msg": f"Удалено: {title}"})
    return RedirectResponse(f"{_base(request)}/{kind.path}?{query}", status_code=303)


# ---------- Ошибки ----------


async def not_found(request: Request, exc: Exception) -> Response:
    status = getattr(exc, "status_code", 404)
    title = "Такой страницы нет" if status == 404 else "Запрос не выполнен"
    return render(request, "message.html", {"title": title}, status)


routes = [
    Route("/", index),
    Route("/login", login, methods=["GET", "POST"]),
    Route("/logout", logout, methods=["POST"]),
    Route("/demo/delete", delete_demo, methods=["POST"]),
    Route("/{kind}", list_items),
    Route("/{kind}/new", edit, methods=["GET"]),
    Route("/{kind}/new", save, methods=["POST"]),
    Route("/{kind}/{item_id}", edit, methods=["GET"]),
    Route("/{kind}/{item_id}", save, methods=["POST"]),
    Route("/{kind}/{item_id}/delete", delete, methods=["POST"]),
]

admin_app = Starlette(routes=routes, exception_handlers={HTTPException: not_found})
