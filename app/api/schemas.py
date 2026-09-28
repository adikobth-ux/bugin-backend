"""Схемы запросов и ответов (pydantic v2) — по контракту ``docs/api.md``.

Имена полей — сразу в camelCase, как в JSON приложения, поэтому псевдонимы не нужны.
Входящие тела терпят лишние поля (``extra="ignore"``) и принимают умолчания
как ``fromJson`` в приложении. Ответы проходят через эти же модели, чтобы
``/docs`` показывал точную схему.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PlaceCategory = Literal[
    "cafe", "coffeeShop", "restaurant", "bowling", "cinema", "park", "gallery", "studio"
]
AmenityType = Literal["wifi", "sockets", "pets", "smoking", "payment", "parking"]
BookingType = Literal["table", "ticket", "lane", "none"]
Occasion = Literal["date", "friends", "work", "family", "solo"]
Vibe = Literal["beautiful", "calm", "active", "novelty"]
EventCategory = Literal["concert", "cinema", "theatre", "exhibition", "workshop", "standup"]
EventDay = Literal["today", "tomorrow", "weekend", "date"]
ParamType = Literal["occasion", "time", "budget", "mood", "location"]
Company = Literal["solo", "pair", "friends", "family"]
PlanDay = Literal["today", "tomorrow", "weekend", "date"]
Mood = Literal["calm", "active", "novelty", "culture"]
StopRole = Literal["coffee", "walk", "dinner", "activity", "culture", "novelty", "work"]
TravelMode = Literal["walk", "taxi"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------- Места и события ----------


class GeoPoint(ApiModel):
    lat: float
    lng: float


class OpeningHours(ApiModel):
    """Минуты от начала суток; ``closesAt`` > 1440 — закрывается после полуночи."""

    opensAt: int
    closesAt: int


class Amenity(ApiModel):
    type: AmenityType
    value: str


class Review(ApiModel):
    author: str
    rating: float
    text: str
    date: str = Field(description="Местное время без смещения: 2026-09-27T12:00:00")


class Place(ApiModel):
    id: str
    name: str
    subtitle: str
    description: str
    category: PlaceCategory
    categoryDetail: str
    address: str
    phone: str
    rating: float
    reviewsCount: int
    priceLevel: int
    averageCheck: int = Field(description="Средний чек на человека, ₸; 0 — бесплатно")
    openingHours: OpeningHours
    photos: list[str]
    tags: list[str]
    amenities: list[Amenity]
    distanceKm: float
    taxiMinutes: int
    bookingType: BookingType
    bookingUrl: str | None = None
    pitch: str
    goodFor: list[Occasion]
    vibes: list[Vibe]
    location: GeoPoint
    reviews: list[Review] = []


class TicketCategory(ApiModel):
    name: str
    price: int


class Event(ApiModel):
    id: str
    title: str
    subtitle: str
    description: str
    category: EventCategory
    startsAt: str = Field(description="Местное время без смещения: 2026-10-03T20:00:00")
    durationMinutes: int
    venueName: str
    address: str
    location: GeoPoint
    distanceKm: float
    priceFrom: int
    image: str = Field(description="Пустая строка — нет картинки")
    tags: list[str]
    ageLimit: int
    tickets: list[TicketCategory]
    pitch: str
    reasons: list[str]
    occasions: list[Occasion]
    vibes: list[Vibe]
    venuePlaceId: str | None = None
    ticketUrl: str | None = None
    isFeatured: bool = False


# ---------- Поиск ----------


class IntentParam(ApiModel):
    type: ParamType
    code: str = Field(description="Код значения; для бюджета — сумма в тенге строкой или «any»")
    inferred: bool = Field(default=False, description="Параметра не было в запросе, сервер додумал")


class SearchIntent(ApiModel):
    query: str = ""
    params: list[IntentParam] = []


class Recommendation(ApiModel):
    kind: Literal["place", "event"]
    place: Place | None = None
    event: Event | None = None
    reason: str
    details: list[str]
    score: float


class UnderstandBody(ApiModel):
    query: str = Field(max_length=1000)


class RecommendBody(ApiModel):
    intent: SearchIntent


# ---------- Вечер ----------


class EveningRequest(ApiModel):
    company: Company = "pair"
    day: PlanDay = "today"
    date: str | None = Field(default=None, description="YYYY-MM-DDT00:00:00 для day=date")
    startMinutes: int = Field(default=19 * 60, ge=0, lt=24 * 60)
    budget: int | None = Field(default=None, ge=0, description="На человека, ₸; null — не важен")
    mood: Mood = "calm"
    wishes: str = Field(default="", max_length=1000)


class TravelLeg(ApiModel):
    mode: TravelMode = "taxi"
    minutes: int = 10


class PlanStop(ApiModel):
    role: StopRole
    placeId: str
    kind: str = Field(default="", description="Код занятия: coffee, walk, dinner, dinner_view…")
    title: str = ""
    kindLabel: str = ""
    startMinutes: int = 0
    durationMinutes: int = 60
    cost: int = 0
    routeLabel: str | None = None
    rating: float | None = None
    image: str = ""


class Scenario(ApiModel):
    id: str
    title: str = ""
    subtitle: str | None = None
    image: str | None = None
    stops: list[PlanStop] = []
    legs: list[TravelLeg] = Field(default=[], description="legs[i] — от stops[i] к stops[i+1]")
    tags: list[str] = []
    request: EveningRequest | None = None


class AlternativesBody(ApiModel):
    scenario: Scenario
    index: int = Field(ge=0)


class ReplaceBody(ApiModel):
    scenario: Scenario
    index: int = Field(ge=0)
    stop: PlanStop


class LocalizeBody(ApiModel):
    scenario: Scenario


# ---------- Служебное ----------


class Health(ApiModel):
    status: str


class ErrorInfo(ApiModel):
    code: Literal["not_found", "bad_request", "internal"]
    message: str


class ErrorResponse(ApiModel):
    error: ErrorInfo


ERROR_RESPONSES: dict[int | str, dict] = {
    400: {"model": ErrorResponse, "description": "Некорректный запрос (bad_request)"},
    404: {"model": ErrorResponse, "description": "Не найдено (not_found)"},
    422: {"model": ErrorResponse, "description": "Тело или параметры не прошли проверку (bad_request)"},
}
