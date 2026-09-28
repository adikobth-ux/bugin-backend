"""Общее для роутеров: язык ответа, ошибки, разбор списка id."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app import lang as language_module


def language(accept_language: str | None = Header(default=None)) -> str:
    """Язык ответа из заголовка Accept-Language: «kk…» → kk, иначе ru."""
    return language_module.from_header(accept_language)


Lang = Annotated[str, Depends(language)]


def not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def split_ids(ids: str) -> list[str]:
    """«a, b,,c» → ["a", "b", "c"]."""
    return [part.strip() for part in ids.split(",") if part.strip()]
