"""Общее для роутеров: язык ответа, ошибки, разбор списка id."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app import lang as language_module


def language(accept_language: str | None = Header(default=None)) -> str:
    """Язык ответа из заголовка Accept-Language: «kk…» → kk, иначе ru."""
    return language_module.from_header(accept_language)


Lang = Annotated[str, Depends(language)]


def user_origin(
    x_bugin_location: str | None = Header(
        default=None,
        description="Где пользователь: «широта,долгота», например 51.128,71.430. "
        "Нет или дальше 60 км от города — расстояния от центра Астаны.",
    ),
) -> tuple[float, float] | None:
    """Положение пользователя из заголовка. Непонятное значение не ошибка — просто нет точки.

    Заголовок, а не параметры адреса: координаты не попадают в журналы запросов.
    """
    if not x_bugin_location:
        return None
    parts = x_bugin_location.split(",")
    if len(parts) != 2:
        return None
    try:
        lat, lng = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):  # NaN тоже не пройдёт
        return None
    return (lat, lng)


UserOrigin = Annotated[tuple[float, float] | None, Depends(user_origin)]


def not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def split_ids(ids: str) -> list[str]:
    """«a, b,,c» → ["a", "b", "c"]."""
    return [part.strip() for part in ids.split(",") if part.strip()]
