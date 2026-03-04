import httpx
from app.core.config import settings


class TiendanubeClient:
    def __init__(self, store_id: str, access_token: str):
        self.store_id = store_id
        self.access_token = access_token

    def _headers(self) -> dict:
        return {
            "Authentication": f"bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "tn-attributes-mvp/1.0",
        }

    async def list_products(self, page: int = 1, per_page: int = 200) -> list[dict]:
        url = f"{settings.TN_API_BASE}/{self.store_id}/products"

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                url,
                headers=self._headers(),
                params={"page": page, "per_page": per_page},
            )
            r.raise_for_status()
            return r.json()
