"""/v1/events — афиша."""

import datetime as dt

from fastapi import APIRouter, Query

from app import clock, services
from app.api.deps import Lang, UserOrigin, bad_request, not_found, split_ids
from app.api.schemas import ERROR_RESPONSES, Event, EventCategory, EventDay

router = APIRouter(prefix="/events", tags=["Афиша"], responses=ERROR_RESPONSES)


@router.get("", response_model=list[Event], summary="События дня или по списку id")
def list_events(
    lang: Lang,
    user: UserOrigin,
    day: EventDay | None = Query(default=None, description="Обязателен, если нет ids"),
    date: dt.date | None = Query(default=None, description="YYYY-MM-DD, для day=date"),
    category: EventCategory | None = Query(default=None),
    ids: str | None = Query(default=None, description="Через запятую, вместо day"),
) -> list[dict]:
    """С ``day`` — события дня по времени начала; с ``ids`` — в порядке ``ids``."""
    catalog = services.catalog()
    if ids is not None:
        return catalog.events_by_ids(lang, split_ids(ids), user)
    if day is None:
        raise bad_request("Укажи day (today, tomorrow, weekend, date) или ids")
    return catalog.events_for_day(lang, clock.now(), day, date, category, user)


@router.get("/featured", response_model=list[Event], summary="Главные события недели")
def featured(lang: Lang, user: UserOrigin) -> list[dict]:
    """``isFeatured`` в ближайшие 7 дней."""
    return services.catalog().featured_events(lang, clock.now(), user)


@router.get("/{event_id}", response_model=Event, summary="Событие")
def by_id(event_id: str, lang: Lang, user: UserOrigin) -> dict:
    event = services.catalog().event(lang, event_id, user)
    if event is None:
        raise not_found(f"Событие {event_id} не найдено")
    return event


@router.get("/{event_id}/similar", response_model=list[Event], summary="Похожие события")
def similar(
    event_id: str, lang: Lang, user: UserOrigin, limit: int = Query(default=4, ge=0, le=100)
) -> list[dict]:
    """Сначала той же категории, затем по времени; без самого события."""
    catalog = services.catalog()
    if catalog.event(lang, event_id) is None:
        raise not_found(f"Событие {event_id} не найдено")
    return catalog.similar_events(lang, clock.now(), event_id, limit, user)
