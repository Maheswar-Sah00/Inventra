"""Outgoing email abstraction used for OTP delivery.

EMAIL_BACKEND=console  -> DEVELOPMENT ONLY: the message (including the OTP) is written to the server log.
EMAIL_BACKEND=smtp     -> sends through the SMTP server configured by the EMAIL_* variables.
"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger("stocksense.email")


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Development-only fallback. Never enable in production (config validation blocks it)."""

    def send(self, to: str, subject: str, body: str) -> None:
        logger.warning("[DEV EMAIL - not sent] To: %s | Subject: %s\n%s", to, subject, body)


class SmtpEmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        s = self.settings
        message = EmailMessage()
        message["From"] = s.EMAIL_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(s.EMAIL_HOST, s.EMAIL_PORT, timeout=15) as smtp:
                if s.EMAIL_USE_TLS:
                    smtp.starttls()
                if s.EMAIL_USERNAME:
                    smtp.login(s.EMAIL_USERNAME, s.EMAIL_PASSWORD)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException):
            # Runs as a background task: log and move on rather than surfacing to the client.
            logger.exception("Failed to send email to %s", to)


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.EMAIL_BACKEND == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()
