import os
import subprocess
from typing import Generator

import pytest
from fastapi.testclient import TestClient


TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/tn_mvp_test",
)

# env mínimo para Settings()
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_URL", "http://localhost:8000")
os.environ.setdefault("FRONTEND_APP_URL", "http://localhost:5173")
os.environ["DB_URL"] = TEST_DB_URL

os.environ.setdefault("TN_CLIENT_ID", "test")
os.environ.setdefault("TN_CLIENT_SECRET", "test")

os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_very_long_value_123")
os.environ.setdefault("JWT_EXPIRES_SECONDS", "3600")

os.environ.setdefault(
    "TOKEN_ENCRYPTION_KEY",
    "KUsp3t8IXzMKvRCqUolo3FM0BPZZFF3wt9eGt5HbfoU=",
)
os.environ.setdefault(
    "OAUTH_STATE_SECRET",
    "test_oauth_state_secret_very_long_value_123",
)


@pytest.fixture(scope="session", autouse=True)
def _migrate_db() -> None:
    subprocess.check_call(["alembic", "upgrade", "head"])


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded_panel_user() -> dict[str, str]:
    from app.core.security import hash_password
    from app.db.models.panel_user import PanelUser
    from app.db.models.product import Product
    from app.db.models.store import Store
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        store_id = "test-store"
        email = "test@example.com"
        password = "test-password-123"

        store = db.get(Store, store_id)
        if store is None:
            store = Store(
                store_id=store_id, access_token="encrypted-token", status="installed"
            )
            db.add(store)

        user = db.query(PanelUser).filter(PanelUser.email == email).first()
        if user is None:
            db.add(
                PanelUser(
                    email=email,
                    password_hash=hash_password(password),
                    store_id=store_id,
                    is_active=True,
                )
            )

        product = db.get(Product, (store_id, "p1"))
        if product is None:
            db.add(
                Product(
                    store_id=store_id,
                    product_id="p1",
                    handle="prod-1",
                    title="Producto 1",
                )
            )

        db.commit()
        return {"store_id": store_id, "email": email, "password": password}
    finally:
        db.close()


@pytest.fixture()
def store_id(seeded_panel_user: dict[str, str]) -> str:
    return seeded_panel_user["store_id"]


@pytest.fixture()
def admin_token(client: TestClient, seeded_panel_user: dict[str, str]) -> str:
    r = client.post(
        "/admin/auth/login",
        json={
            "email": seeded_panel_user["email"],
            "password": seeded_panel_user["password"],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
