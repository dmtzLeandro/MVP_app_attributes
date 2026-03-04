import os
import json
import httpx
from dotenv import load_dotenv

# Carga el .env de la raíz del proyecto (ejecutando desde la raíz)
load_dotenv(".env")

TN_API_BASE = os.getenv("TN_API_BASE")  # ej: https://api.tiendanube.com/2025-03
USER_AGENT = os.getenv("USER_AGENT", "tn-mvp/0.1")

token_path = os.path.join("app", "tiendanube_connector", "token.json")
with open(token_path, "r", encoding="utf-8") as f:
    token = json.load(f)

access_token = token.get("access_token")
store_id = token.get("user_id") or os.getenv("STORE_ID")

if not TN_API_BASE:
    raise RuntimeError(
        "TN_API_BASE is missing. Set it in .env (e.g. https://api.tiendanube.com/2025-03)."
    )

if not store_id:
    raise RuntimeError(
        "STORE_ID is missing. Set STORE_ID in .env or ensure token.json has user_id."
    )

if not access_token:
    raise RuntimeError("access_token is missing in token.json.")

# Normaliza base si alguien lo puso sin protocolo (por las dudas)
if not TN_API_BASE.startswith("http"):
    TN_API_BASE = "https://" + TN_API_BASE.lstrip("/")

url = f"{TN_API_BASE}/{store_id}/products"

print("TN_API_BASE:", TN_API_BASE)
print("STORE_ID:", store_id)
print("ACCESS_TOKEN:", str(access_token)[:10] + "...")

r = httpx.get(
    url,
    headers={
        "Authentication": f"bearer {access_token}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    },
    params={"page": 1, "per_page": 1},
    timeout=30,
)

print("STATUS:", r.status_code)
print("BODY:", r.text[:1000])
