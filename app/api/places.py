"""/v1/places — места."""

from fastapi import APIRouter, Query

from app import clock
from app.api.deps import Lang, not_found, split_ids
from app.api.schemas import ERROR_RESPONSES, Place
from app.domain import catalog

router = APIRouter(prefix="/places", tags=["Места"], responses=ERROR_RESPONSES)


@router.get("/nearby", response_model=list[Place], summary="Места рядом")
def nearby(
    lang: Lang,
    limit: int = Query(default=6, ge=0, le=100),
    lat: float | None = Query(default=None, description="На этапе 0 не учитывается"),
    lng: float | None = Query(default=None, description="На этапе 0 не учитывается"),
) -> list[dict]:
    """Блок «Сейчас рядом» на главной — в порядке «рядом»."""
    return catalog.nearby(lang, clock.now(), limit)


@router.get("", response_model=list[Place], summary="Места по списку id")
def by_ids(lang: Lang, ids: str = Query(..., description="Через запятую: a,b,c")) -> list[dict]:
    """Места в порядке ``ids``; неизвестные id пропускаются."""
    return catalog.places_by_ids(lang, clock.now(), split_ids(ids))


@router.get("/{place_id}", response_model=Place, summary="Место")
def by_id(place_id: str, lang: Lang) -> dict:
    place = catalog.place(lang, clock.now(), place_id)
    if place is None:
        raise not_found(f"Место {place_id} не найдено")
    return place
