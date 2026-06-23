from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.import_products import (
    pick_main_image_src,
    tn_i18n_to_str,
    tn_parse_dt,
)
from app.services.thumbnails import image_src_hash as calc_src_hash
from app.tiendanube_connector.client import TiendanubeClient

logger = logging.getLogger("app.sync")


async def _resolve_image_src(
    client: TiendanubeClient,
    *,
    product_id: str,
    raw_product: dict[str, Any],
    current_image_src: str | None,
    store_id: str,
) -> str | None:
    images = raw_product.get("images")

    if isinstance(images, list):
        return pick_main_image_src(images)

    if current_image_src:
        return current_image_src

    try:
        imgs = await client.list_product_images(product_id=product_id)
        return pick_main_image_src(imgs)
    except Exception:
        logger.warning(
            "sync_product_images_fallback_failed",
            extra={"store_id": store_id, "product_id": product_id},
        )
        return None


async def sync_products(
    db: Session, store_id: str, access_token: str
) -> dict[str, int | str | bool]:
    client = TiendanubeClient(store_id=store_id, access_token=access_token)

    page = 1
    per_page = 200

    inserted = 0
    updated = 0
    unchanged = 0
    deactivated = 0
    reactivated = 0
    total_remote = 0

    total_local_before = db.query(Product).filter(Product.store_id == store_id).count()

    remote_ids: set[str] = set()

    logger.info("sync_started", extra={"store_id": store_id})

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
            remote_ids.add(product_id)
            total_remote += 1

            handle = tn_i18n_to_str(p.get("handle"))
            title = tn_i18n_to_str(p.get("name") or p.get("title"))
            tn_updated_at = tn_parse_dt(p.get("updated_at"))

            obj = db.get(Product, (store_id, product_id))
            current_image_src = obj.image_src if obj is not None else None
            src = await _resolve_image_src(
                client,
                product_id=product_id,
                raw_product=p,
                current_image_src=current_image_src,
                store_id=store_id,
            )
            src_hash = calc_src_hash(src) if src else None

            if obj is None:
                db.add(
                    Product(
                        store_id=store_id,
                        product_id=product_id,
                        handle=handle,
                        title=title,
                        tn_updated_at=tn_updated_at,
                        image_src=src,
                        image_src_hash=src_hash,
                        is_active=True,
                    )
                )
                inserted += 1
                continue

            was_inactive = obj.is_active is False
            changed = (
                obj.handle != handle
                or obj.title != title
                or obj.tn_updated_at != tn_updated_at
                or obj.image_src != src
                or obj.image_src_hash != src_hash
            )

            obj.handle = handle
            obj.title = title
            obj.tn_updated_at = tn_updated_at
            obj.image_src = src
            obj.image_src_hash = src_hash
            obj.is_active = True

            if was_inactive:
                reactivated += 1
            elif changed:
                updated += 1
            else:
                unchanged += 1

        db.commit()

        logger.info(
            "sync_page_done",
            extra={"store_id": store_id, "page": page, "fetched_count": len(items)},
        )
        page += 1

    to_deactivate = (
        db.query(Product)
        .filter(Product.store_id == store_id, Product.is_active.is_(True))
        .all()
    )

    for obj in to_deactivate:
        if obj.product_id in remote_ids:
            continue
        obj.is_active = False
        deactivated += 1

    db.commit()

    result = {
        "ok": True,
        "store_id": store_id,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deactivated": deactivated,
        "reactivated": reactivated,
        "total_remote": total_remote,
        "total_local_before": total_local_before,
    }

    logger.info("sync_finished", extra=result)
    return result
