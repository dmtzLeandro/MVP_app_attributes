from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.tiendanube_connector.client import TiendanubeClient


def tn_i18n_to_str(value: Any) -> str:
    """
    Tiendanube a veces devuelve campos como dict por idioma: {"es": "..."}.
    Esta función normaliza a string.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # prioridad: español, si no, primer string disponible
        if "es" in value and isinstance(value["es"], str):
            return value["es"]
        for v in value.values():
            if isinstance(v, str):
                return v
        return ""
    return str(value)


def tn_parse_dt(value: Any):
    """
    Convierte strings tipo '2026-02-22T19:29:42+0000' a datetime.
    Si no se puede parsear, devuelve None.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value
        # '+0000' -> '+00:00'
        if len(s) >= 5 and (s[-5] in ["+", "-"]) and s[-2:].isdigit():
            s = s[:-2] + ":" + s[-2:]
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


async def seed_products(db: Session, store_id: str, access_token: str) -> int:
    client = TiendanubeClient(store_id=store_id, access_token=access_token)

    page = 1
    per_page = 200
    inserted_or_updated = 0

    while True:
        try:
            items = await client.list_products(page=page, per_page=per_page)
        except httpx.HTTPStatusError as e:
            # Tiendanube devuelve 404 cuando pedís una página > last_page
            # Ej: {"code":404,"message":"Not Found","description":"Last page is 5"}
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

            # PK compuesta: (store_id, product_id)
            obj = db.get(Product, (store_id, product_id))
            if obj is None:
                obj = Product(
                    store_id=store_id,
                    product_id=product_id,
                    handle=handle,
                    title=title,
                    tn_updated_at=tn_updated_at,
                )
                db.add(obj)
            else:
                obj.handle = handle
                obj.title = title
                obj.tn_updated_at = tn_updated_at

            inserted_or_updated += 1

        db.commit()
        page += 1

    return inserted_or_updated
