from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__("Email delivery failed")
        self.reason = reason


def smtp_is_configured() -> bool:
    host = (settings.SMTP_HOST or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    return bool(host and from_email)


def send_email(*, to_email: str, subject: str, html: str, text: str) -> None:
    host = (settings.SMTP_HOST or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    from_name = (settings.SMTP_FROM_NAME or "").strip()
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
