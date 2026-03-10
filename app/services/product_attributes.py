from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.db.models.product_attribute_value import ProductAttributeValue


logger = logging.getLogger("app.attributes")

MVP_KEYS = ("ancho_cm", "composicion")


def parse_ancho_cm(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_attrs_map(
    db: Session, store_id: str, product_ids: list[str]
) -> dict[tuple[str, str], str]:
    """
    1 query: (product_id, attribute_key) -> value
    Filtra por store_id, product_ids y las keys del MVP.
    """
    if not product_ids:
        return {}

    rows = (
        db.query(ProductAttributeValue)
        .filter(
            ProductAttributeValue.store_id == store_id,
            ProductAttributeValue.product_id.in_(product_ids),
            ProductAttributeValue.attribute_key.in_(list(MVP_KEYS)),
        )
        .all()
    )
    return {(r.product_id, r.attribute_key): r.value for r in rows}


def upsert_one(
    db: Session, store_id: str, product_id: str, key: str, value: str | None
) -> str:
    """
    Replica EXACTAMENTE la semántica existente:
    - None o "" => delete
    - else => upsert
    Devuelve: "deleted" | "inserted" | "updated" | "noop"
    """
    if value is None or value == "":
        deleted = (
            db.query(ProductAttributeValue)
            .filter_by(store_id=store_id, product_id=product_id, attribute_key=key)
            .delete()
        )
        return "deleted" if deleted else "noop"

    row = (
        db.query(ProductAttributeValue)
        .filter_by(store_id=store_id, product_id=product_id, attribute_key=key)
        .one_or_none()
    )

    if row is None:
        db.add(
            ProductAttributeValue(
                store_id=store_id,
                product_id=product_id,
                attribute_key=key,
                value=str(value),
            )
        )
        return "inserted"

    if row.value != str(value):
        row.value = str(value)
        return "updated"

    return "noop"


def read_attrs_out(
    store_id: str, product_id: str, attrs_map: dict[tuple[str, str], str]
) -> dict:
    """
    Devuelve dict compatible con ProductAttributesOut.
    """
    ancho_raw = attrs_map.get((product_id, "ancho_cm"))
    comp_raw = attrs_map.get((product_id, "composicion"))
    return {
        "product_id": product_id,
        "store_id": store_id,
        "ancho_cm": parse_ancho_cm(ancho_raw),
        "composicion": comp_raw,
    }


def batch_get(db: Session, store_id: str, product_ids: list[str]) -> dict[str, object]:
    """
    Asume product_ids ya validados (existentes).
    Devuelve payload 'items' listo.
    """
    attrs_map = get_attrs_map(db, store_id=store_id, product_ids=product_ids)
    items = [read_attrs_out(store_id, pid, attrs_map) for pid in product_ids]
    return {"items": items}


def batch_upsert(
    db: Session,
    store_id: str,
    items: list[dict],
    existing_ids: set[str],
) -> dict[str, object]:
    """
    items: lista de dict con keys: product_id, ancho_cm, composicion
    existing_ids: set de product_id válidos (ya validados por caller)
    No hace commit aquí: el caller controla commit/rollback.
    Devuelve contadores y items_out (read-back).
    """
    inserted = updated = deleted = 0
    product_ids_in_order: list[str] = []
    received = len(items)

    for it in items:
        pid = it["product_id"]
        if pid not in existing_ids:
            continue

        if pid not in product_ids_in_order:
            product_ids_in_order.append(pid)

        r1 = upsert_one(
            db,
            store_id=store_id,
            product_id=pid,
            key="ancho_cm",
            value=str(it["ancho_cm"]) if it.get("ancho_cm") is not None else None,
        )
        r2 = upsert_one(
            db,
            store_id=store_id,
            product_id=pid,
            key="composicion",
            value=it.get("composicion"),
        )

        for r in (r1, r2):
            if r == "inserted":
                inserted += 1
            elif r == "updated":
                updated += 1
            elif r == "deleted":
                deleted += 1

    # read-back en 1 query
    attrs_map = get_attrs_map(db, store_id=store_id, product_ids=product_ids_in_order)
    items_out = [
        read_attrs_out(store_id, pid, attrs_map) for pid in product_ids_in_order
    ]

    logger.info(
        "batch_upsert",
        extra={
            "store_id": store_id,
            "received": received,
            "inserted": inserted,
            "updated": updated,
            "deleted": deleted,
            "missing_products": max(0, received - len(product_ids_in_order)),
        },
    )

    return {
        "inserted": inserted,
        "updated": updated,
        "deleted": deleted,
        "items_out": items_out,
        "product_ids": product_ids_in_order,
    }
