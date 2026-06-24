import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import _build_cors_origins, app


@pytest.fixture(scope="session", autouse=True)
def _migrate_db() -> None:
    """CORS tests do not need the database migration from the shared fixtures."""


def test_cors_origins_normalize_frontend_url_and_filter_empty_values():
    assert _build_cors_origins("https://frontend.example.test/") == [
        "http://localhost:5173",
        "https://frontend.example.test",
    ]
    assert _build_cors_origins("  ") == ["http://localhost:5173"]


def test_cors_preflight_allows_configured_frontend():
    assert settings.FRONTEND_APP_URL is not None
    origin = settings.FRONTEND_APP_URL.strip().rstrip("/")
    client = TestClient(app)

    response = client.options(
        "/admin/auth/register",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    client.close()
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_admin_preflight_rejects_unconfigured_storefront_origin():
    client = TestClient(app)

    response = client.options(
        "/admin/auth/register",
        headers={
            "Origin": "https://shop.example.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    client.close()
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_storefront_preflight_allows_external_origin_without_credentials():
    client = TestClient(app)

    response = client.options(
        "/admin/storefront/attributes/batch",
        headers={
            "Origin": "https://shop.example.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    client.close()
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-methods"] == "POST, OPTIONS"
    assert response.headers["access-control-allow-headers"] == "content-type"
    assert "access-control-allow-credentials" not in response.headers


def test_storefront_validation_error_keeps_public_cors_without_credentials():
    client = TestClient(app)

    response = client.post(
        "/admin/storefront/attributes/batch",
        headers={"Origin": "https://shop.example.test"},
        json={},
    )

    client.close()
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers
