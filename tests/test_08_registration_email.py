import logging
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.admin_api import routes_auth
from app.admin_api.routes_auth import RegisterIn
from app.services import email as email_service
from app.services.email import EmailDeliveryError


@pytest.fixture(scope="session", autouse=True)
def _migrate_db() -> None:
    """These unit tests do not need the shared PostgreSQL migration fixture."""


class QueryStub:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def delete(self, *args, **kwargs):
        return 0


class DbStub:
    def __init__(self):
        self.added = []
        self.committed = False

    def get(self, model, key):
        return SimpleNamespace(status="installed")

    def query(self, model):
        return QueryStub()

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


class FakeSmtp:
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.starttls_called = False
        self.login_args = None
        self.sent_messages = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def starttls(self):
        self.starttls_called = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.sent_messages.append(message)


@pytest.fixture(autouse=True)
def isolate_registration(monkeypatch):
    monkeypatch.setattr(routes_auth, "rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        routes_auth,
        "hash_password",
        lambda value: "test-password-hash",
    )
    monkeypatch.setattr(
        routes_auth.secrets,
        "token_urlsafe",
        lambda size: "test-verification-token",
    )
    monkeypatch.setattr(
        routes_auth.settings,
        "APP_URL",
        "https://backend.example.test/",
    )


def perform_registration():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/auth/register",
            "headers": [],
        }
    )
    payload = RegisterIn(
        store_id="test-store",
        email="panel@example.com",
        password="test-password-123",
        password_confirm="test-password-123",
    )
    db = DbStub()

    result = routes_auth.register(request=request, payload=payload, db=db)

    assert db.committed is True
    assert len(db.added) == 1
    return result


def test_smtp_not_configured_in_staging_returns_fallback_url(monkeypatch):
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "staging")
    monkeypatch.setattr(routes_auth, "smtp_is_configured", lambda: False)

    def unexpected_send(**kwargs):
        pytest.fail("Email delivery must not be attempted")

    monkeypatch.setattr(
        routes_auth,
        "send_registration_verification_email",
        unexpected_send,
    )

    result = perform_registration()

    assert result.ok is True
    assert result.pending is True
    assert result.email_sent is False
    assert result.verification_sent is False
    assert result.verification_url is not None
    assert result.verification_url.startswith(
        "https://backend.example.test/admin/auth/verify-email?token="
    )


def test_smtp_configured_and_delivery_ok_does_not_return_fallback_url(monkeypatch):
    sent = {}

    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "staging")
    monkeypatch.setattr(routes_auth, "smtp_is_configured", lambda: True)

    def fake_send(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr(
        routes_auth,
        "send_registration_verification_email",
        fake_send,
    )

    result = perform_registration()

    assert result.ok is True
    assert result.pending is True
    assert result.email_sent is True
    assert result.verification_sent is True
    assert result.verification_url is None
    assert sent["to_email"] == "panel@example.com"
    assert sent["verification_url"].startswith(
        "https://backend.example.test/admin/auth/verify-email?token="
    )


def test_smtp_not_configured_in_production_does_not_expose_url(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "production")
    monkeypatch.setattr(routes_auth, "smtp_is_configured", lambda: False)
    caplog.set_level(logging.ERROR, logger=routes_auth.__name__)

    result = perform_registration()

    assert result.ok is True
    assert result.pending is True
    assert result.email_sent is False
    assert result.verification_sent is False
    assert result.verification_url is None
    assert result.message == (
        "La cuenta quedó pendiente de verificación. "
        "Si no recibís el email, contactá a soporte."
    )
    assert "registration_verification_email_not_configured" in caplog.text
    assert "test-verification-token" not in caplog.text
    assert "panel@example.com" not in caplog.text
    assert "https://backend.example.test" not in caplog.text


def test_smtp_delivery_failure_in_production_is_safe(monkeypatch, caplog):
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "production")
    monkeypatch.setattr(routes_auth, "smtp_is_configured", lambda: True)

    def fail_delivery(**kwargs):
        raise EmailDeliveryError("SMTPAuthenticationError")

    monkeypatch.setattr(
        routes_auth,
        "send_registration_verification_email",
        fail_delivery,
    )
    caplog.set_level(logging.ERROR, logger=routes_auth.__name__)

    result = perform_registration()

    assert result.ok is True
    assert result.pending is True
    assert result.email_sent is False
    assert result.verification_sent is False
    assert result.verification_url is None
    assert result.message == (
        "La cuenta quedó pendiente de verificación. "
        "Si no recibís el email, contactá a soporte."
    )
    assert "registration_verification_email_failed" in caplog.text
    assert any(
        getattr(record, "delivery_error", None) == "SMTPAuthenticationError"
        for record in caplog.records
    )
    assert "test-verification-token" not in caplog.text
    assert "panel@example.com" not in caplog.text
    assert "https://backend.example.test" not in caplog.text


def test_password_reset_email_still_uses_send_email(monkeypatch):
    FakeSmtp.instances.clear()

    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(email_service.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", "smtp-user")
    monkeypatch.setattr(email_service.settings, "SMTP_PASSWORD", "smtp-password")
    monkeypatch.setattr(
        email_service.settings,
        "SMTP_FROM_EMAIL",
        "no-reply@example.com",
    )
    monkeypatch.setattr(
        email_service.settings,
        "SMTP_FROM_NAME",
        "TN Attributes App",
    )
    monkeypatch.setattr(email_service.settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(email_service.settings, "SMTP_TIMEOUT_SECONDS", 10)
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSmtp)

    email_service.send_password_reset_email(
        to_email="panel@example.com",
        reset_url=(
            "https://frontend.example.test/"
            "reset-password?token=test-reset-token"
        ),
    )

    assert len(FakeSmtp.instances) == 1
    smtp = FakeSmtp.instances[0]
    assert smtp.host == "smtp.example.test"
    assert smtp.port == 587
    assert smtp.timeout == 10
    assert smtp.starttls_called is True
    assert smtp.login_args == ("smtp-user", "smtp-password")
    assert len(smtp.sent_messages) == 1

    message = smtp.sent_messages[0]
    assert message["To"] == "panel@example.com"
    assert message["From"] == "TN Attributes App <no-reply@example.com>"
    assert "Restablecé tu contraseña" in message["Subject"]
