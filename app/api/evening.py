"""/v1/evening — «Собрать мне вечер»."""

from fastapi import APIRouter

from app import clock, services
from app.api.deps import Lang, UserOrigin, bad_request, not_found
from app.api.schemas import (
    ERROR_RESPONSES,
    AlternativesBody,
    EveningRequest,
    LocalizeBody,
    PlanStop,
    ReplaceBody,
    Scenario,
)
from app.domain.planner import EveningPlanner, request_from_json, scenario_from_json, stop_from_json

router = APIRouter(prefix="/evening", tags=["Вечер"], responses=ERROR_RESPONSES)


def _planner(lang: str, user: tuple[float, float] | None = None) -> EveningPlanner:
    # С точкой пользователя ближние к нему места идут в план первыми.
    return EveningPlanner(lang, services.catalog().places(lang, user))


@router.post("/plan", response_model=Scenario, summary="Собрать план")
def plan(body: EveningRequest, lang: Lang, user: UserOrigin) -> dict:
    """План в рамках бюджета по компании, времени и настроению."""
    return _planner(lang, user).plan(request_from_json(body.model_dump()))


@router.post("/alternatives", response_model=list[PlanStop], summary="Замены точки")
def alternatives(body: AlternativesBody, lang: Lang, user: UserOrigin) -> list[dict]:
    """Чем заменить точку ``index`` в рамках бюджета."""
    scenario = scenario_from_json(body.scenario.model_dump())
    try:
        return _planner(lang, user).alternatives(scenario, body.index)
    except IndexError as error:
        raise bad_request(str(error)) from error


@router.post("/replace", response_model=Scenario, summary="Заменить точку")
def replace(body: ReplaceBody, lang: Lang) -> dict:
    """Ставит ``stop`` на место ``index`` и пересчитывает время и переезды."""
    scenario = scenario_from_json(body.scenario.model_dump())
    stop = stop_from_json(body.stop.model_dump())
    try:
        return _planner(lang).replace_stop(scenario, body.index, stop)
    except IndexError as error:
        raise bad_request(str(error)) from error


@router.get("/featured", response_model=Scenario, summary="Для тебя сегодня")
def featured(lang: Lang, user: UserOrigin) -> dict:
    """До 16:00 — спокойный рабочий день, позже — спокойный вечер вдвоём."""
    scenario = _planner(lang, user).featured(clock.now())
    if not scenario["stops"]:
        raise not_found("В каталоге пока нет мест для плана")
    return scenario


@router.post("/localize", response_model=Scenario, summary="Перевести план")
def localize(body: LocalizeBody, lang: Lang) -> dict:
    """Тот же план (точки, время, цены) с текстами на языке запроса."""
    return _planner(lang).localize(scenario_from_json(body.scenario.model_dump()))
