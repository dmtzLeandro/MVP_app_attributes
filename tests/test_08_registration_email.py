import json
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
    """These unit tests do not need the shared PostgreSQL fixture."""


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


class FakeWebhookResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size):
        return self.body[:size]


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


@pytest.fixture
def configured_google_apps_script(monkeypatch):
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_PROVIDER",
        "google_apps_script",
    )
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_WEBHOOK_URL",
        "https://script.google.com/macros/s/test/exec",
    )
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_WEBHOOK_SECRET",
        "test-webhook-secret",
    )
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_FROM_NAME",
        "TN Attributes App",
    )
    monkeypatch.setattr(email_service.settings, "EMAIL_TIMEOUT_SECONDS", 10)


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


def assert_sensitive_values_absent(caplog):
    log_text = caplog.text
    assert "test-verification-token" not in log_text
    assert "panel@example.com" not in log_text
    assert "https://backend.example.test" not in log_text
    assert "test-webhook-secret" not in log_text


def test_provider_not_configured_in_staging_returns_fallback_url(monkeypatch):
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "staging")
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: False,
    )

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


def test_configured_provider_and_delivery_ok_has_no_fallback_url(monkeypatch):
    sent = {}
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "staging")
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: True,
    )

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


def test_provider_failure_in_staging_returns_fallback_url(monkeypatch, caplog):
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "staging")
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: True,
    )

    def fail_delivery(**kwargs):
        raise EmailDeliveryError("google_apps_script_connection_error")

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
    assert result.verification_url is not None
    assert result.verification_url.startswith(
        "https://backend.example.test/admin/auth/verify-email?token="
    )
    assert "registration_verification_email_failed" in caplog.text
    assert any(
        getattr(record, "delivery_error", None)
        == "google_apps_script_connection_error"
        for record in caplog.records
    )
    assert_sensitive_values_absent(caplog)


def test_provider_not_configured_in_production_does_not_expose_url(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "production")
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: False,
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
    assert "registration_email_provider_not_configured" in caplog.text
    assert_sensitive_values_absent(caplog)


def test_provider_failure_in_production_is_safe(monkeypatch, caplog):
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "production")
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: True,
    )

    def fail_delivery(**kwargs):
        raise EmailDeliveryError("google_apps_script_rejected")

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
        getattr(record, "delivery_error", None)
        == "google_apps_script_rejected"
        for record in caplog.records
    )
    assert_sensitive_values_absent(caplog)


class FakeRawWebhookResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size):
        return self.body[:size]


class PasswordResetQueryStub:
    def __init__(self, first_value=None):
        self.first_value = first_value

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_value

    def all(self):
        return []


class PasswordResetDbStub:
    def __init__(self):
        self.user = SimpleNamespace(
            id=1,
            email="panel@example.com",
            store_id="test-store",
            is_active=True,
        )
        self.added = []
        self.committed = False

    def query(self, model):
        if model.__name__ == "PanelUser":
            return PasswordResetQueryStub(self.user)
        return PasswordResetQueryStub()

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


def test_google_apps_script_configuration_requires_secret(monkeypatch):
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_PROVIDER",
        "google_apps_script",
    )
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_WEBHOOK_URL",
        "https://script.google.com/macros/s/test/exec",
    )
    monkeypatch.setattr(email_service.settings, "EMAIL_WEBHOOK_SECRET", None)

    assert email_service.google_apps_script_is_configured() is False
    assert email_service.email_provider_is_configured() is False


def test_google_apps_script_configuration_requires_https_exec_url(monkeypatch):
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_PROVIDER",
        "google_apps_script",
    )
    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_WEBHOOK_SECRET",
        "test-webhook-secret",
    )

    invalid_urls = [
        "http://script.google.com/macros/s/test/exec",
        "https://example.com/macros/s/test/exec",
        "https://script.google.com/macros/s/test/dev",
        "https://user:password@script.google.com/macros/s/test/exec",
        "https://script.google.com/macros/s/test/exec#fragment",
    ]

    for webhook_url in invalid_urls:
        monkeypatch.setattr(
            email_service.settings,
            "EMAIL_WEBHOOK_URL",
            webhook_url,
        )
        assert email_service.google_apps_script_is_configured() is False
        assert email_service.email_provider_is_configured() is False

    monkeypatch.setattr(
        email_service.settings,
        "EMAIL_WEBHOOK_URL",
        "https://script.google.com/macros/s/test/exec",
    )
    assert email_service.google_apps_script_is_configured() is True
    assert email_service.email_provider_is_configured() is True


def test_google_apps_script_sends_expected_payload(
    monkeypatch,
    configured_google_apps_script,
):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeWebhookResponse({"ok": True})

    monkeypatch.setattr(email_service, "urlopen", fake_urlopen)

    email_service.send_registration_verification_email(
        to_email="panel@example.com",
        verification_url=(
            "https://backend.example.test/"
            "admin/auth/verify-email?token=test-token"
        ),
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "https://script.google.com/macros/s/test/exec"
    assert captured["timeout"] == 10
    assert captured["payload"]["version"] == 1
    assert captured["payload"]["secret"] == "test-webhook-secret"
    assert captured["payload"]["to"] == "panel@example.com"
    assert captured["payload"]["subject"] == "Verificá tu cuenta"
    assert captured["payload"]["from_name"] == "TN Attributes App"
    assert "test-token" in captured["payload"]["text"]
    assert "test-token" in captured["payload"]["html"]

    normalized_headers = {
        key.lower(): value for key, value in captured["headers"].items()
    }
    assert normalized_headers["content-type"] == "application/json"
    assert normalized_headers["accept"] == "application/json"


def test_google_apps_script_rejected_response_raises(
    monkeypatch,
    configured_google_apps_script,
):
    monkeypatch.setattr(
        email_service,
        "urlopen",
        lambda request, timeout: FakeWebhookResponse(
            {"ok": False, "error": "delivery_failed"}
        ),
    )

    with pytest.raises(
        EmailDeliveryError,
        match="Email delivery failed",
    ) as exc_info:
        email_service.send_email(
            to_email="panel@example.com",
            subject="Test",
            text="Plain text",
            html="<p>HTML</p>",
        )

    assert exc_info.value.reason == "google_apps_script_rejected"


def test_google_apps_script_invalid_json_response_raises(
    monkeypatch,
    configured_google_apps_script,
):
    monkeypatch.setattr(
        email_service,
        "urlopen",
        lambda request, timeout: FakeRawWebhookResponse(b"not-json"),
    )

    with pytest.raises(EmailDeliveryError) as exc_info:
        email_service.send_email(
            to_email="panel@example.com",
            subject="Test",
            text="Plain text",
            html="<p>HTML</p>",
        )

    assert exc_info.value.reason == "google_apps_script_invalid_response"


def test_google_apps_script_oversized_response_raises(
    monkeypatch,
    configured_google_apps_script,
):
    oversized_body = b"x" * (email_service.MAX_WEBHOOK_RESPONSE_BYTES + 1)
    monkeypatch.setattr(
        email_service,
        "urlopen",
        lambda request, timeout: FakeRawWebhookResponse(oversized_body),
    )

    with pytest.raises(EmailDeliveryError) as exc_info:
        email_service.send_email(
            to_email="panel@example.com",
            subject="Test",
            text="Plain text",
            html="<p>HTML</p>",
        )

    assert exc_info.value.reason == "google_apps_script_response_too_large"


@pytest.mark.parametrize(
    "connection_error",
    [
        email_service.URLError("simulated connection failure"),
        TimeoutError("simulated timeout"),
        OSError("simulated operating system error"),
    ],
)
def test_google_apps_script_connection_errors_are_wrapped(
    monkeypatch,
    configured_google_apps_script,
    connection_error,
):
    def fail_connection(request, timeout):
        raise connection_error

    monkeypatch.setattr(email_service, "urlopen", fail_connection)

    with pytest.raises(EmailDeliveryError) as exc_info:
        email_service.send_email(
            to_email="panel@example.com",
            subject="Test",
            text="Plain text",
            html="<p>HTML</p>",
        )

    assert exc_info.value.reason == "google_apps_script_connection_error"


def test_google_apps_script_http_error_is_wrapped(
    monkeypatch,
    configured_google_apps_script,
):
    def fail_request(request, timeout):
        raise email_service.HTTPError(
            url=request.full_url,
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(email_service, "urlopen", fail_request)

    with pytest.raises(EmailDeliveryError) as exc_info:
        email_service.send_email(
            to_email="panel@example.com",
            subject="Test",
            text="Plain text",
            html="<p>HTML</p>",
        )

    assert exc_info.value.reason == "google_apps_script_http_error"


def test_password_reset_uses_google_apps_script_provider(
    monkeypatch,
    configured_google_apps_script,
):
    captured = {}

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return FakeWebhookResponse({"ok": True})

    monkeypatch.setattr(email_service, "urlopen", fake_urlopen)

    email_service.send_password_reset_email(
        to_email="panel@example.com",
        reset_url=(
            "https://frontend.example.test/"
            "reset-password?token=test-reset-token"
        ),
    )

    assert captured["version"] == 1
    assert captured["secret"] == "test-webhook-secret"
    assert captured["to"] == "panel@example.com"
    assert captured["subject"] == "Restablecé tu contraseña"
    assert captured["from_name"] == "TN Attributes App"
    assert "test-reset-token" in captured["text"]
    assert "test-reset-token" in captured["html"]


def test_forgot_password_with_google_apps_script_success(
    monkeypatch,
    configured_google_apps_script,
):
    captured = {}
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: True,
    )

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return FakeWebhookResponse({"ok": True})

    monkeypatch.setattr(email_service, "urlopen", fake_urlopen)
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "staging")
    monkeypatch.setattr(
        routes_auth.settings,
        "FRONTEND_APP_URL",
        "https://frontend.example.test",
    )

    db = PasswordResetDbStub()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/auth/forgot-password",
            "headers": [],
        }
    )
    payload = routes_auth.ForgotPasswordIn(email="panel@example.com")

    result = routes_auth.forgot_password(request=request, payload=payload, db=db)

    assert db.committed is True
    assert len(db.added) == 1
    assert result.ok is True
    assert result.reset_sent is True
    assert result.reset_url is None
    assert captured["to"] == "panel@example.com"
    assert "reset-password?token=" in captured["text"]
    assert "reset-password?token=" in captured["html"]


def test_forgot_password_provider_failure_in_staging_returns_fallback(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "staging")
    monkeypatch.setattr(
        routes_auth.settings,
        "FRONTEND_APP_URL",
        "https://frontend.example.test",
    )

    def fail_delivery(**kwargs):
        raise EmailDeliveryError("google_apps_script_connection_error")

    monkeypatch.setattr(routes_auth, "send_password_reset_email", fail_delivery)
    caplog.set_level(logging.ERROR, logger=routes_auth.__name__)

    db = PasswordResetDbStub()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/auth/forgot-password",
            "headers": [],
        }
    )
    payload = routes_auth.ForgotPasswordIn(email="panel@example.com")

    result = routes_auth.forgot_password(request=request, payload=payload, db=db)

    assert result.ok is True
    assert result.reset_sent is False
    assert result.reset_url is not None
    assert result.reset_url.startswith(
        "https://frontend.example.test/reset-password?token="
    )
    assert "password_reset_email_failed" in caplog.text
    assert_sensitive_values_absent(caplog)


def test_forgot_password_provider_failure_in_production_is_safe(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        routes_auth,
        "email_provider_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(routes_auth.settings, "APP_ENV", "production")
    monkeypatch.setattr(
        routes_auth.settings,
        "FRONTEND_APP_URL",
        "https://frontend.example.test",
    )

    def fail_delivery(**kwargs):
        raise EmailDeliveryError("google_apps_script_rejected")

    monkeypatch.setattr(routes_auth, "send_password_reset_email", fail_delivery)
    caplog.set_level(logging.ERROR, logger=routes_auth.__name__)

    db = PasswordResetDbStub()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/auth/forgot-password",
            "headers": [],
        }
    )
    payload = routes_auth.ForgotPasswordIn(email="panel@example.com")

    result = routes_auth.forgot_password(request=request, payload=payload, db=db)

    assert result.ok is True
    assert result.reset_sent is False
    assert result.reset_url is None
    assert result.message == "If the email exists, a reset link has been sent."
    assert "password_reset_email_failed" in caplog.text
    assert_sensitive_values_absent(caplog)


def test_password_reset_email_still_supports_smtp(monkeypatch):
    FakeSmtp.instances.clear()
    monkeypatch.setattr(email_service.settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email_service.settings, "EMAIL_FROM_NAME", None)
    monkeypatch.setattr(
        email_service.settings,
        "SMTP_HOST",
        "smtp.example.test",
    )
    monkeypatch.setattr(email_service.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", "smtp-user")
    monkeypatch.setattr(
        email_service.settings,
        "SMTP_PASSWORD",
        "smtp-password",
    )
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
