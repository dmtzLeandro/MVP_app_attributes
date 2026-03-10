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
os.environ["DB_URL"] = TEST_DB_URL

os.environ.setdefault("TN_CLIENT_ID", "test")
os.environ.setdefault("TN_CLIENT_SECRET", "test")

# admin auth for tests
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_very_long_value_123")
os.environ.setdefault("JWT_EXPIRES_SECONDS", "3600")

# crypto keys required by Settings
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
    # Corre alembic upgrade head contra tn_mvp_test
    subprocess.check_call(["alembic", "upgrade", "head"])


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def store_id() -> str:
    return "test-store"


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    r = client.post(
        "/admin/auth/login", json={"username": "admin", "password": "admin"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
