from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.store import Store
from app.tiendanube_connector.oauth import build_authorize_url, exchange_code_for_token
from app.services.import_products import seed_products

from app.admin_api.routes_products import router as admin_products_router
from app.admin_api.routes_import_export import router as admin_csv_router

app = FastAPI(title="TN Materiales MVP", version="0.1.0")

# CORS (DEMO Vite)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_products_router)
app.include_router(admin_csv_router)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/auth/install")
def auth_install():
    # MVP: state fijo o simple. En producción: state firmado/CSRF.
    state = "mvp"
    return {"authorize_url": build_authorize_url(state=state)}


@app.get("/auth/callback")
async def auth_callback(
    request: Request, code: str, state: str | None = None, db: Session = Depends(get_db)
):
    token = await exchange_code_for_token(code)
    store_id = str(token["user_id"])
    access_token = token["access_token"]

    obj = db.get(Store, store_id)
    if obj is None:
        obj = Store(store_id=store_id, access_token=access_token, status="installed")
        db.add(obj)
    else:
        obj.access_token = access_token
        obj.status = "installed"

    db.commit()

    # Seed inmediato (MVP). Alternativa: endpoint manual.
    imported = await seed_products(db=db, store_id=store_id, access_token=access_token)

    return {"ok": True, "store_id": store_id, "products_seeded": imported}
