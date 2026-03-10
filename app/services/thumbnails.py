from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx
from PIL import Image, ImageOps

from app.core.config import settings


def image_src_hash(src: str) -> str:
    # hash estable y corto para querystring + comparación
    return hashlib.sha1(src.encode("utf-8")).hexdigest()


def thumbs_root() -> Path:
    root = (
        getattr(settings, "THUMB_CACHE_DIR", None)
        or os.getenv("THUMB_CACHE_DIR")
        or "var/thumbs"
    )
    return Path(root)


def thumb_path(store_id: str, product_id: str) -> Path:
    return thumbs_root() / store_id / f"{product_id}.webp"


async def download_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.content


def render_thumb_webp(img_bytes: bytes, size: int) -> bytes:
    # Fit (crop center) para tener thumb cuadrado prolijo
    with Image.open(io_bytes := _BytesIO(img_bytes)) as im:
        im = im.convert("RGB")
        thumb = ImageOps.fit(
            im, (size, size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
        out = _BytesIO()
        thumb.save(out, format="WEBP", quality=70, method=6)
        return out.getvalue()


class _BytesIO:
    # mini wrapper para evitar importar io en todo el archivo en tu estilo
    def __init__(self, b: bytes = b""):
        import io

        self._bio = io.BytesIO(b)

    def __getattr__(self, name):
        return getattr(self._bio, name)


async def ensure_thumbnail(
    *,
    store_id: str,
    product_id: str,
    image_url_1024: str,
    size: int,
) -> Path:
    """
    Genera (o regenera) thumbnail webp y lo guarda pisando el archivo.
    Devuelve la ruta.
    """
    p = thumb_path(store_id, product_id)
    p.parent.mkdir(parents=True, exist_ok=True)

    raw = await download_bytes(image_url_1024)
    webp = render_thumb_webp(raw, size=size)

    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(webp)
    tmp.replace(p)

    return p
