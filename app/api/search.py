"""/v1/search — AI-поиск (пока — правила по ключевым словам)."""

from fastapi import APIRouter

from app import clock, services
from app.api.deps import Lang, not_found
from app.api.schemas import (
    ERROR_RESPONSES,
    Recommendation,
    RecommendBody,
    SearchIntent,
    UnderstandBody,
)
from app.domain.search import SearchService, parse

router = APIRouter(prefix="/search", tags=["Поиск"], responses=ERROR_RESPONSES)


def _service(lang: str) -> SearchService:
    catalog = services.catalog()
    return SearchService(lang, catalog.places(lang), catalog.events(lang))


@router.post("/understand", response_model=SearchIntent, summary="Понять запрос")
def understand(body: UnderstandBody) -> dict:
    """Текст → параметры (повод, время, бюджет, настроение, где искать)."""
    return parse(body.query, clock.now())


@router.post("/recommend", response_model=list[Recommendation], summary="Подобрать варианты")
def recommend(body: RecommendBody, lang: Lang) -> list[dict]:
    """Места и сегодняшние события по параметрам — по убыванию ``score``."""
    return _service(lang).rank(body.intent.model_dump(), clock.now())


@router.get("/surprise", response_model=Recommendation, summary="Удиви меня")
def surprise(lang: Lang) -> dict:
    """Случайный хороший вариант."""
    item = _service(lang).surprise(clock.now())
    if item is None:
        raise not_found("Сейчас нечего предложить")
    return item
