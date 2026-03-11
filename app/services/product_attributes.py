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


def get_attr_rows_map(
    db: Session, store_id: str, product_ids: list[str]
) -> dict[tuple[str, str], ProductAttributeValue]:
    """
    1 query: (product_id, attribute_key) -> ORM row
    Útil para upsert batch sin reconsultas por item y sin inserts ciegos.
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
    return {(r.product_id, r.attribute_key): r for r in rows}


def upsert_one(
    db: Session, store_id: str, product_id: str, key: str, value: str | None
) -> str:
    """
    Semántica:
    - None o "" => delete
    - else => upsert
    Devuelve: "deleted" | "inserted" | "updated" | "noop"
    """
    row = (
        db.query(ProductAttributeValue)
        .filter_by(store_id=store_id, product_id=product_id, attribute_key=key)
        .one_or_none()
    )

    if value is None or value == "":
        if row is None:
            return "noop"
        db.delete(row)
        return "deleted"

    value_str = str(value)

    if row is None:
        db.add(
            ProductAttributeValue(
                store_id=store_id,
                product_id=product_id,
                attribute_key=key,
                value=value_str,
            )
        )
        return "inserted"

    if row.value != value_str:
        row.value = value_str
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

    valid_items: list[dict] = []
    for it in items:
        pid = it["product_id"]
        if pid not in existing_ids:
            continue
        valid_items.append(it)
        if pid not in product_ids_in_order:
            product_ids_in_order.append(pid)

    # Precargar rows existentes una sola vez para evitar inserts ciegos y conflictos.
    rows_map = get_attr_rows_map(
        db, store_id=store_id, product_ids=product_ids_in_order
    )

    for it in valid_items:
        pid = it["product_id"]

        incoming_values = {
            "ancho_cm": str(it["ancho_cm"]) if it.get("ancho_cm") is not None else None,
            "composicion": it.get("composicion"),
        }

        for key in MVP_KEYS:
            incoming = incoming_values[key]
            map_key = (pid, key)
            row = rows_map.get(map_key)

            # Delete si viene vacío/null
            if incoming is None or incoming == "":
                if row is not None:
                    db.delete(row)
                    deleted += 1
                    rows_map.pop(map_key, None)
                continue

            incoming_str = str(incoming)

            # Insert si no existe
            if row is None:
                new_row = ProductAttributeValue(
                    store_id=store_id,
                    product_id=pid,
                    attribute_key=key,
                    value=incoming_str,
                )
                db.add(new_row)
                rows_map[map_key] = new_row
                inserted += 1
                continue

            # Update si cambió
            if row.value != incoming_str:
                row.value = incoming_str
                updated += 1

    # Flush explícito para detectar conflictos acá y no recién en commit.
    db.flush()

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
