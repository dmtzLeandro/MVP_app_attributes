from app.db.models.panel_user_password_reset import PanelUserPasswordReset
from app.db.session import SessionLocal


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
    forgot = client.post(
        "/admin/auth/forgot-password",
        json={"email": seeded_panel_user["email"]},
    )
    assert forgot.status_code == 200, forgot.text

    reset_url = forgot.json()["reset_url"]
    assert reset_url

    token = reset_url.split("token=")[1]

    reset = client.post(
        "/admin/auth/reset-password",
        json={
            "token": token,
            "password": "new-password-123",
            "password_confirm": "new-password-123",
        },
    )
    assert reset.status_code == 200, reset.text

    login = client.post(
        "/admin/auth/login",
        json={
            "email": seeded_panel_user["email"],
            "password": "new-password-123",
        },
    )
    assert login.status_code == 200, login.text


def test_reset_password_reused_token_fails(client, seeded_panel_user):
    forgot = client.post(
        "/admin/auth/forgot-password",
        json={"email": seeded_panel_user["email"]},
    )
    assert forgot.status_code == 200, forgot.text

    token = forgot.json()["reset_url"].split("token=")[1]

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
