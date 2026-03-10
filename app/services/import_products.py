from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.tiendanube_connector.client import TiendanubeClient
from app.services.thumbnails import image_src_hash as calc_src_hash

logger = logging.getLogger("app.seed")


def tn_i18n_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "es" in value and isinstance(value["es"], str):
            return value["es"]
        for v in value.values():
            if isinstance(v, str):
                return v
        return ""
    return str(value)


def tn_parse_dt(value: Any):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value
        if len(s) >= 5 and (s[-5] in ["+", "-"]) and s[-2:].isdigit():
            s = s[:-2] + ":" + s[-2:]
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def pick_main_image_src(images: list[dict[str, Any]]) -> str | None:
    if not images:
        return None
    pos1 = next((img for img in images if img.get("position") == 1), None)
    chosen = pos1 or images[0]
    src = chosen.get("src")
    return str(src) if src else None


async def seed_products(db: Session, store_id: str, access_token: str) -> int:
    client = TiendanubeClient(store_id=store_id, access_token=access_token)

    page = 1
    per_page = 200
    inserted_or_updated = 0

    logger.info("seed_started", extra={"store_id": store_id})

    while True:
        try:
            items = await client.list_products(page=page, per_page=per_page)
        except httpx.HTTPStatusError as e:
            body = e.response.text or ""
            if e.response.status_code == 404 and "Last page is" in body:
                break
            raise

        if not items:
            break

        for p in items:
            product_id = str(p["id"])
            handle = tn_i18n_to_str(p.get("handle"))
            title = tn_i18n_to_str(p.get("name") or p.get("title"))
            tn_updated_at = tn_parse_dt(p.get("updated_at"))

            obj = db.get(Product, (store_id, product_id))
            if obj is None:
                obj = Product(
                    store_id=store_id,
                    product_id=product_id,
                    handle=handle,
                    title=title,
                    tn_updated_at=tn_updated_at,
                    image_src=None,
                    image_src_hash=None,
                )
                db.add(obj)
            else:
                obj.handle = handle
                obj.title = title
                obj.tn_updated_at = tn_updated_at

            # Best-effort: traer imagen principal solo si no tenemos o si está vacía
            if not obj.image_src:
                try:
                    imgs = await client.list_product_images(product_id=product_id)
                    src = pick_main_image_src(imgs)
                    obj.image_src = src
                    obj.image_src_hash = calc_src_hash(src) if src else None
                except Exception:
                    obj.image_src = None
                    obj.image_src_hash = None
            else:
                # asegurar hash presente si ya había src
                if obj.image_src and not obj.image_src_hash:
                    obj.image_src_hash = calc_src_hash(obj.image_src)

            inserted_or_updated += 1

        db.commit()

        logger.info(
            "seed_page_done",
            extra={"store_id": store_id, "page": page, "fetched_count": len(items)},
        )
        page += 1

    logger.info(
        "seed_finished",
        extra={"store_id": store_id, "total_imported": inserted_or_updated},
    )
    return inserted_or_updated
