from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
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


class _BytesIO:
    # mini wrapper para evitar importar io en todo el archivo en tu estilo
    def __init__(self, b: bytes = b""):
        import io

        self._bio = io.BytesIO(b)

    def __getattr__(self, name):
        return getattr(self._bio, name)


# -------------------------
# CONCURRENCIA Y TIMEOUTS
# -------------------------


def _thumb_gen_max_concurrency() -> int:
    raw = (
        getattr(settings, "THUMB_GEN_MAX_CONCURRENCY", None)
        or os.getenv("THUMB_GEN_MAX_CONCURRENCY")
        or "2"
    )
    try:
        value = int(raw)
    except Exception:
        value = 2
    return max(1, value)


def _thumb_acquire_timeout_seconds() -> float:
    raw = (
        getattr(settings, "THUMB_ACQUIRE_TIMEOUT_SECONDS", None)
        or os.getenv("THUMB_ACQUIRE_TIMEOUT_SECONDS")
        or "0.20"
    )
    try:
        value = float(raw)
    except Exception:
        value = 0.20
    return max(0.01, value)


def _thumb_connect_timeout_seconds() -> float:
    raw = (
        getattr(settings, "THUMB_CONNECT_TIMEOUT_SECONDS", None)
        or os.getenv("THUMB_CONNECT_TIMEOUT_SECONDS")
        or "3.0"
    )
    try:
        value = float(raw)
    except Exception:
        value = 3.0
    return max(0.5, value)


def _thumb_read_timeout_seconds() -> float:
    raw = (
        getattr(settings, "THUMB_READ_TIMEOUT_SECONDS", None)
        or os.getenv("THUMB_READ_TIMEOUT_SECONDS")
        or "6.0"
    )
    try:
        value = float(raw)
    except Exception:
        value = 6.0
    return max(0.5, value)


_THUMB_GEN_SEMAPHORE = asyncio.Semaphore(_thumb_gen_max_concurrency())
_THUMB_KEY_LOCKS: dict[str, asyncio.Lock] = {}
_THUMB_KEY_LOCKS_GUARD = asyncio.Lock()


async def _get_key_lock(key: str) -> asyncio.Lock:
    async with _THUMB_KEY_LOCKS_GUARD:
        lock = _THUMB_KEY_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _THUMB_KEY_LOCKS[key] = lock
        return lock


async def download_bytes(url: str) -> bytes:
    timeout = httpx.Timeout(
        connect=_thumb_connect_timeout_seconds(),
        read=_thumb_read_timeout_seconds(),
        write=10.0,
        pool=10.0,
    )
    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
    )

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.content


def render_thumb_webp(img_bytes: bytes, size: int) -> bytes:
    # Fit (crop center) para tener thumb cuadrado prolijo
    with Image.open(_BytesIO(img_bytes)) as im:
        im = im.convert("RGB")
        thumb = ImageOps.fit(
            im,
            (size, size),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        out = _BytesIO()
        thumb.save(out, format="WEBP", quality=70, method=6)
        return out.getvalue()


async def _write_bytes_atomic(target: Path, payload: bytes, prefix: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f"{prefix}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        Path(tmp_name).replace(target)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass


async def ensure_thumbnail(
    *,
    store_id: str,
    product_id: str,
    image_url_1024: str,
    size: int,
) -> Path | None:
    """
    Best-effort thumbnail generation.

    - Si ya existe, devuelve la ruta inmediatamente.
    - Si el servidor está ocupado, devuelve None rápido.
    - Si consigue slot, genera la miniatura y la guarda.
    """
    p = thumb_path(store_id, product_id)
    if p.exists():
        return p

    acquire_timeout = _thumb_acquire_timeout_seconds()

    try:
        await asyncio.wait_for(_THUMB_GEN_SEMAPHORE.acquire(), timeout=acquire_timeout)
    except asyncio.TimeoutError:
        # Sin capacidad inmediata: degradar rápido y no bloquear el panel.
        return None

    try:
        key = f"{store_id}:{product_id}:{size}"
        lock = await _get_key_lock(key)

        async with lock:
            # Doble chequeo por si otro request la generó antes.
            if p.exists():
                return p

            raw = await download_bytes(image_url_1024)
            webp = await asyncio.to_thread(render_thumb_webp, raw, size)
            await _write_bytes_atomic(p, webp, prefix=f"{product_id}-{size}")

            return p if p.exists() else None
    finally:
        _THUMB_GEN_SEMAPHORE.release()
