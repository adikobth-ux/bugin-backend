"""/v1/places — места."""

from fastapi import APIRouter, Query

from app import services
from app.api.deps import Lang, UserOrigin, not_found, split_ids
from app.api.schemas import ERROR_RESPONSES, Place

router = APIRouter(prefix="/places", tags=["Места"], responses=ERROR_RESPONSES)


@router.get("/nearby", response_model=list[Place], summary="Места рядом")
def nearby(
    lang: Lang,
    user: UserOrigin,
    limit: int = Query(default=6, ge=0, le=100),
    lat: float | None = Query(default=None, ge=-90, le=90, description="Где пользователь"),
    lng: float | None = Query(default=None, ge=-180, le=180, description="Где пользователь"),
) -> list[dict]:
    """Блок «Сейчас рядом»: ближайшие к пользователю (``lat``/``lng`` или заголовок
    ``X-Bugin-Location``), без них — к центру Астаны."""
    origin = (lat, lng) if lat is not None and lng is not None else user
    return services.catalog().nearby(lang, limit, origin)


@router.get("", response_model=list[Place], summary="Места по списку id")
def by_ids(
    lang: Lang, user: UserOrigin, ids: str = Query(..., description="Через запятую: a,b,c")
) -> list[dict]:
    """Места в порядке ``ids``; неизвестные id пропускаются."""
    return services.catalog().places_by_ids(lang, split_ids(ids), user)


@router.get("/{place_id}", response_model=Place, summary="Место")
def by_id(place_id: str, lang: Lang, user: UserOrigin) -> dict:
    place = services.catalog().place(lang, place_id, user)
    if place is None:
        raise not_found(f"Место {place_id} не найдено")
    return place
