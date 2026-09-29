"""Фото из админки: уменьшить, повернуть по EXIF, сохранить JPEG в хранилище.

Снимок с телефона (4000×3000, 5 МБ) превращается в JPEG до 1600 px по длинной
стороне — около 200–400 КБ: быстро грузится в приложении и не съедает базу.
"""

import io
import secrets

from PIL import Image, ImageOps, UnidentifiedImageError

from app.domain.catalog import IMAGE_PATH
from app.storage.base import Store

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_SIDE = 1600
QUALITY = 82

# Защита от «картинок-бомб» на десятки тысяч пикселей по стороне.
Image.MAX_IMAGE_PIXELS = 60_000_000


class PhotoError(ValueError):
    """Файл не подошёл; текст — для админки."""


def process(data: bytes) -> tuple[bytes, int, int]:
    """Любая картинка → (JPEG, ширина, высота)."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoError("Файл больше 20 МБ")
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            return out.getvalue(), image.width, image.height
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
        raise PhotoError("Не получилось открыть картинку — нужен JPEG, PNG или WebP") from error


def save(store: Store, data: bytes) -> str:
    """Сохраняет фото, возвращает путь ``/v1/images/<id>.jpg``."""
    jpeg, width, height = process(data)
    image_id = secrets.token_hex(8)
    store.save_image(image_id, "image/jpeg", jpeg, width, height)
    return f"{IMAGE_PATH}{image_id}.jpg"


def image_id(url: str) -> str | None:
    """``/v1/images/abc.jpg`` или полная ссылка на него → ``abc``; чужая ссылка → None."""
    marker = url.find(IMAGE_PATH)
    if marker < 0:
        return None
    name = url[marker + len(IMAGE_PATH):]
    name = name.split("?")[0].removesuffix(".jpg")
    return name if name and all(ch in "0123456789abcdef" for ch in name) else None


def referenced(store: Store) -> set[str]:
    """id фото, на которые ссылаются записи каталога (фото может быть у копий события)."""
    ids: set[str] = set()
    for kind in ("place", "event"):
        for record in store.records(kind):
            for url in list(record.doc.get("photos") or []) + [record.doc.get("image") or ""]:
                found = image_id(url) if isinstance(url, str) else None
                if found:
                    ids.add(found)
    return ids


def delete_unused(store: Store, urls: list[str]) -> None:
    """Удаляет фото из ``urls``, если на них больше никто не ссылается."""
    ids = {found for url in urls if (found := image_id(url))}
    if ids:
        store.delete_images(sorted(ids - referenced(store)))
