from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def smtp_is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


def send_email(*, to_email: str, subject: str, html: str, text: str) -> None:
    if not smtp_is_configured():
        raise RuntimeError("SMTP is not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (
        f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        if settings.SMTP_FROM_NAME
        else settings.SMTP_FROM_EMAIL
    )
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    if settings.SMTP_USE_TLS:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return

    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)


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
        <p>
          <a href="{verification_url}" style="display:inline-block;padding:12px 18px;background:#16324f;color:#ffffff;text-decoration:none;border-radius:8px;">
            Verificar email
          </a>
        </p>
        <p>Si el botón no funciona, copiá este enlace:</p>
        <p>{verification_url}</p>
        <p>Si no fuiste vos, ignorá este mensaje.</p>
      </body>
    </html>
    """.strip()

    send_email(
        to_email=to_email,
        subject=subject,
        html=html,
        text=text,
    )
