from datetime import datetime, timedelta

import pytest

from app.admin_api import routes_auth
from app.db.models.panel_user_password_reset import PanelUserPasswordReset
from app.db.session import SessionLocal


@pytest.fixture(autouse=True)
def isolate_password_reset(monkeypatch):
    monkeypatch.setattr(routes_auth, "rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: False,
    )


def request_password_reset(client, email: str) -> str:
    response = client.post(
        "/admin/auth/forgot-password",
        json={"email": email},
    )
    assert response.status_code == 200, response.text

    reset_url = response.json()["reset_url"]
    assert reset_url
    return reset_url.rsplit("token=", 1)[1]


def test_forgot_password_existing_user_returns_ok(client, seeded_panel_user):
    r = client.post(
        "/admin/auth/forgot-password",
        json={"email": seeded_panel_user["email"]},
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["ok"] is True
    assert "message" in data
    assert "reset_url" in data

    db = SessionLocal()
    try:
        row = (
            db.query(PanelUserPasswordReset)
            .filter(PanelUserPasswordReset.email == seeded_panel_user["email"])
            .first()
        )
        assert row is not None
        assert row.is_used is False
    finally:
        db.close()


def test_forgot_password_unknown_email_does_not_leak(client):
    r = client.post(
        "/admin/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["ok"] is True
    assert "message" in data


def test_reset_password_valid_token_changes_password(client, seeded_panel_user):
    token = request_password_reset(client, seeded_panel_user["email"])

    reset = client.post(
        "/admin/auth/reset-password",
        json={
            "token": token,
            "password": "new-password-123",
            "password_confirm": "new-password-123",
        },
    )
    assert reset.status_code == 200, reset.text

    db = SessionLocal()
    try:
        row = (
            db.query(PanelUserPasswordReset)
            .filter(PanelUserPasswordReset.email == seeded_panel_user["email"])
            .order_by(PanelUserPasswordReset.id.desc())
            .first()
        )
        assert row is not None
        assert row.is_used is True
        assert row.used_at is not None
    finally:
        db.close()

    login = client.post(
        "/admin/auth/login",
        json={
            "email": seeded_panel_user["email"],
            "password": "new-password-123",
        },
    )
    assert login.status_code == 200, login.text


def test_reset_password_reused_token_fails(client, seeded_panel_user):
    token = request_password_reset(client, seeded_panel_user["email"])

    first = client.post(
        "/admin/auth/reset-password",
        json={
            "token": token,
            "password": "new-password-123",
            "password_confirm": "new-password-123",
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/admin/auth/reset-password",
        json={
            "token": token,
            "password": "another-password-123",
            "password_confirm": "another-password-123",
        },
    )
    assert second.status_code == 400, second.text
    assert second.json()["error"]["code"] == "RESET_TOKEN_ALREADY_USED"


def test_reset_password_expired_token_fails(client, seeded_panel_user):
    token = request_password_reset(client, seeded_panel_user["email"])

    db = SessionLocal()
    try:
        row = (
            db.query(PanelUserPasswordReset)
            .filter(PanelUserPasswordReset.email == seeded_panel_user["email"])
            .order_by(PanelUserPasswordReset.id.desc())
            .first()
        )
        assert row is not None
        row.reset_expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/admin/auth/reset-password",
        json={
            "token": token,
            "password": "new-password-123",
            "password_confirm": "new-password-123",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "RESET_TOKEN_EXPIRED"


def test_reset_password_unknown_token_fails(client):
    response = client.post(
        "/admin/auth/reset-password",
        json={
            "token": "nonexistent-reset-token",
            "password": "new-password-123",
            "password_confirm": "new-password-123",
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "INVALID_RESET_TOKEN"


def test_new_reset_invalidates_previous_token(client, seeded_panel_user):
    first_token = request_password_reset(client, seeded_panel_user["email"])
    second_token = request_password_reset(client, seeded_panel_user["email"])

    previous = client.post(
        "/admin/auth/reset-password",
        json={
            "token": first_token,
            "password": "new-password-123",
            "password_confirm": "new-password-123",
        },
    )

    assert previous.status_code == 400, previous.text
    assert previous.json()["error"]["code"] == "RESET_TOKEN_ALREADY_USED"

    latest = client.post(
        "/admin/auth/reset-password",
        json={
            "token": second_token,
            "password": "new-password-123",
            "password_confirm": "new-password-123",
        },
    )

    assert latest.status_code == 200, latest.text
