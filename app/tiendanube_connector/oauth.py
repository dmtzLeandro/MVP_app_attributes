from urllib.parse import urlencode
import httpx
from app.core.config import settings

def build_authorize_url(state: str) -> str:
    # Docs: /apps/{app_id}/authorize?state=...  :contentReference[oaicite:3]{index=3}
    base = f"{settings.TN_OAUTH_BASE}/apps/{settings.TN_CLIENT_ID}/authorize"
    return f"{base}?{urlencode({'state': state})}"

async def exchange_code_for_token(code: str) -> dict:
    url = f"{settings.TN_OAUTH_BASE}/apps/authorize/token"  # :contentReference[oaicite:4]{index=4}
    payload = {
        "client_id": settings.TN_CLIENT_ID,
        "client_secret": settings.TN_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        return r.json()