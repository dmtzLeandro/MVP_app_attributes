from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.config import settings


class TiendanubeClient:
    def __init__(self, *, store_id: str, access_token: str):
        self.store_id = store_id
        self.access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authentication": f"bearer {self.access_token}",
            "User-Agent": "tn-attributes-mvp/1.0",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        url = f"{settings.TN_API_BASE}/{self.store_id}{path}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            r = await client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()

    async def list_products(
        self, *, page: int = 1, per_page: int = 200
    ) -> list[dict[str, Any]]:
        data = await self._get("/products", params={"page": page, "per_page": per_page})
        return data

    async def list_product_images(self, *, product_id: str) -> list[dict[str, Any]]:
        # Endpoint oficial: /products/{id}/images. Respuesta contiene `src`.
        data = await self._get(f"/products/{product_id}/images")
        return data
