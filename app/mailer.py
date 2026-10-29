import asyncio
import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import Settings


def _send_message(settings: Settings, message: EmailMessage) -> None:
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


async def send_booking_confirmation(settings: Settings, booking: dict[str, Any]) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise ValueError("Configura SMTP_HOST y SMTP_FROM_EMAIL para enviar correos.")
    if bool(settings.smtp_username) != bool(settings.smtp_password):
        raise ValueError("Configura SMTP_USERNAME y SMTP_PASSWORD juntos.")

    message = EmailMessage()
    message["Subject"] = f"Tu ruta ha sido confirmada - {settings.business_name}"
    message["From"] = settings.smtp_from_email
    message["To"] = booking["email"]
    if settings.contact_email:
        message["Reply-To"] = settings.contact_email
    message.set_content(
        f"""Hola {booking['nombre_completo']},

Nos alegra confirmarte que tu solicitud de ruta fue aceptada con éxito.
Tu reserva {booking['codigo_reserva']} para {booking['experiencia_nombre']}
ha sido confirmada para el {booking['fecha_solicitada']} con
{booking['numero_participantes']} participante(s).

Gracias por elegir {settings.business_name}. Si necesitas más información
o tienes alguna consulta, puedes responder a este correo.

¡Te esperamos para vivir una gran experiencia!

Atentamente,
El equipo de {settings.business_name}"""
    )
    await asyncio.to_thread(_send_message, settings, message)
