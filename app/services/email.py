from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import settings


MAX_WEBHOOK_RESPONSE_BYTES = 64 * 1024


class EmailDeliveryError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__("Email delivery failed")
        self.reason = reason


def _email_provider() -> str:
    return settings.EMAIL_PROVIDER.strip().lower()


def smtp_is_configured() -> bool:
    host = (settings.SMTP_HOST or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    return bool(host and from_email)


def google_apps_script_is_configured() -> bool:
    webhook_url = (settings.EMAIL_WEBHOOK_URL or "").strip()
    webhook_secret = (settings.EMAIL_WEBHOOK_SECRET or "").strip()

    if not webhook_url or not webhook_secret:
        return False

    parsed = urlparse(webhook_url)

    return (
        parsed.scheme == "https"
        and parsed.hostname == "script.google.com"
        and parsed.path.endswith("/exec")
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )


def email_provider_is_configured() -> bool:
    provider = _email_provider()

    if provider == "smtp":
        return smtp_is_configured()

    if provider == "google_apps_script":
        return google_apps_script_is_configured()

    return False


def _email_from_name() -> str:
    return (
        (settings.EMAIL_FROM_NAME or "").strip()
        or (settings.SMTP_FROM_NAME or "").strip()
        or "TN Attributes App"
    )


def send_email(
    *,
    to_email: str,
    subject: str,
    html: str,
    text: str,
) -> None:
    provider = _email_provider()

    if provider == "smtp":
        _send_via_smtp(
            to_email=to_email,
            subject=subject,
            html=html,
            text=text,
        )
        return

    if provider == "google_apps_script":
        _send_via_google_apps_script(
            to_email=to_email,
            subject=subject,
            html=html,
            text=text,
        )
        return

    raise EmailDeliveryError("email_provider_unsupported")


def _send_via_smtp(
    *,
    to_email: str,
    subject: str,
    html: str,
    text: str,
) -> None:
    host = (settings.SMTP_HOST or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    from_name = _email_from_name()
    username = (settings.SMTP_USERNAME or "").strip()
    password = settings.SMTP_PASSWORD or ""

    if not host or not from_email:
        raise EmailDeliveryError("smtp_not_configured")

    if bool(username) != bool(password):
        raise EmailDeliveryError("smtp_credentials_incomplete")

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = to_email
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        timeout = int(settings.SMTP_TIMEOUT_SECONDS)

        if settings.SMTP_USE_TLS:
            with smtplib.SMTP(
                host,
                settings.SMTP_PORT,
                timeout=timeout,
            ) as server:
                server.starttls()
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
            return

        with smtplib.SMTP_SSL(
            host,
            settings.SMTP_PORT,
            timeout=timeout,
        ) as server:
            if username and password:
                server.login(username, password)
            server.send_message(msg)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise EmailDeliveryError(type(exc).__name__) from exc


def _send_via_google_apps_script(
    *,
    to_email: str,
    subject: str,
    html: str,
    text: str,
) -> None:
    webhook_url = (settings.EMAIL_WEBHOOK_URL or "").strip()
    webhook_secret = (settings.EMAIL_WEBHOOK_SECRET or "").strip()

    if not google_apps_script_is_configured():
        raise EmailDeliveryError("google_apps_script_not_configured")

    payload = {
        "version": 1,
        "secret": webhook_secret,
        "to": to_email,
        "subject": subject,
        "text": text,
        "html": html,
        "from_name": _email_from_name(),
    }

    request = Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "tn-attributes-email/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=int(settings.EMAIL_TIMEOUT_SECONDS),
        ) as response:
            response_body = response.read(MAX_WEBHOOK_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise EmailDeliveryError("google_apps_script_http_error") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise EmailDeliveryError("google_apps_script_connection_error") from exc

    if len(response_body) > MAX_WEBHOOK_RESPONSE_BYTES:
        raise EmailDeliveryError("google_apps_script_response_too_large")

    try:
        response_payload = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EmailDeliveryError("google_apps_script_invalid_response") from exc

    if (
        not isinstance(response_payload, dict)
        or response_payload.get("ok") is not True
    ):
        raise EmailDeliveryError("google_apps_script_rejected")


def send_registration_verification_email(
    *, to_email: str, verification_url: str
) -> None:
    subject = "Verificá tu cuenta"
    text = (
        "Recibimos una solicitud para crear tu cuenta en TN Attributes App.\n\n"
        f"Verificá tu email desde este enlace:\n{verification_url}\n\n"
        "Si no fuiste vos, ignorá este mensaje."
    )
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #16324f;">
        <h2>Verificá tu cuenta</h2>
        <p>Recibimos una solicitud para crear tu cuenta en <strong>TN Attributes App</strong>.</p>
        <p>Antes de ingresar al panel, necesitás validar tu cuenta desde este enlace:</p>
        <p>
          <a href="{verification_url}" style="display:inline-block;padding:12px 18px;background:#16324f;color:#ffffff;text-decoration:none;border-radius:8px;">
            Validar cuenta
          </a>
        </p>
        <p>Si el botón no funciona, copiá este enlace:</p>
        <p>{verification_url}</p>
        <p>Si no fuiste vos, ignorá este mensaje.</p>
      </body>
    </html>
    """.strip()

    send_email(to_email=to_email, subject=subject, html=html, text=text)


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    subject = "Restablecé tu contraseña"
    text = (
        "Recibimos una solicitud para restablecer tu contraseña en TN Attributes App.\n\n"
        f"Usá este enlace para definir una nueva contraseña:\n{reset_url}\n\n"
        "Si no fuiste vos, ignorá este mensaje."
    )
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #16324f;">
        <h2>Restablecé tu contraseña</h2>
        <p>Recibimos una solicitud para restablecer tu contraseña en <strong>TN Attributes App</strong>.</p>
        <p>
          <a href="{reset_url}" style="display:inline-block;padding:12px 18px;background:#16324f;color:#ffffff;text-decoration:none;border-radius:8px;">
            Restablecer contraseña
          </a>
        </p>
        <p>Si el botón no funciona, copiá este enlace:</p>
        <p>{reset_url}</p>
        <p>Si no fuiste vos, ignorá este mensaje.</p>
      </body>
    </html>
    """.strip()

    send_email(to_email=to_email, subject=subject, html=html, text=text)
