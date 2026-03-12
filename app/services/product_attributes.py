from __future__ import annotations

import logging

from sqlalchemy import delete, func, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    inserted = updated = deleted_count = 0
    received = len(items)

    product_ids_in_order: list[str] = []
    final_by_product: dict[str, dict[str, str | None]] = {}

    for it in items:
        pid = it["product_id"]
        if pid not in existing_ids:
            continue

        if pid not in final_by_product:
            product_ids_in_order.append(pid)

        final_by_product[pid] = {
            "ancho_cm": (
                str(it["ancho_cm"]) if it.get("ancho_cm") is not None else None
            ),
            "composicion": it.get("composicion"),
        }

    existing_map = get_attrs_map(
        db, store_id=store_id, product_ids=product_ids_in_order
    )

    delete_pairs: list[tuple[str, str]] = []
    upsert_rows: list[dict[str, str]] = []

    for pid in product_ids_in_order:
        incoming_values = final_by_product[pid]

        for key in MVP_KEYS:
            incoming = incoming_values[key]
            existing = existing_map.get((pid, key))

            if incoming is None or incoming == "":
                if existing is not None:
                    delete_pairs.append((pid, key))
                    deleted_count += 1
                continue

            incoming_str = str(incoming)

            if existing is None:
                inserted += 1
                upsert_rows.append(
                    {
                        "store_id": store_id,
                        "product_id": pid,
                        "attribute_key": key,
                        "value": incoming_str,
                    }
                )
                continue

            if existing != incoming_str:
                updated += 1
                upsert_rows.append(
                    {
                        "store_id": store_id,
                        "product_id": pid,
                        "attribute_key": key,
                        "value": incoming_str,
                    }
                )

    if delete_pairs:
        db.execute(
            delete(ProductAttributeValue).where(
                ProductAttributeValue.store_id == store_id,
                tuple_(
                    ProductAttributeValue.product_id,
                    ProductAttributeValue.attribute_key,
                ).in_(delete_pairs),
            )
        )

    if upsert_rows:
        stmt = pg_insert(ProductAttributeValue).values(upsert_rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_store_product_attr",
            set_={
                "value": stmt.excluded.value,
                "updated_at": func.now(),
            },
        )
        db.execute(stmt)

    db.flush()

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
            "deleted": deleted_count,
            "missing_products": max(0, received - len(product_ids_in_order)),
        },
    )

    return {
        "inserted": inserted,
        "updated": updated,
        "deleted": deleted_count,
        "items_out": items_out,
        "product_ids": product_ids_in_order,
    }
