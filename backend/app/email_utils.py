"""Minimal SMTP email sending."""

import logging
import smtplib
from email.message import EmailMessage

from app import config

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email, or log it when SMTP isn't configured (dev/test)."""
    if not config.SMTP_HOST:
        logger.info("SMTP not configured; skipping email to %s: %s", to, subject)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.SMTP_FROM
    message["To"] = to
    message.set_content(body)

    # 465 is implicit TLS; anything else (587) upgrades with STARTTLS.
    if config.SMTP_PORT == 465:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
    else:
        smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
    with smtp as conn:
        if config.SMTP_PORT != 465:
            conn.starttls()
        if config.SMTP_USER and config.SMTP_PASSWORD:
            conn.login(config.SMTP_USER, config.SMTP_PASSWORD)
        conn.send_message(message)


def send_email_safely(to: str, subject: str, body: str) -> None:
    """``send_email`` for background tasks: a mail failure is logged, not raised."""
    try:
        send_email(to, subject, body)
    except Exception:
        logger.exception("sending email to %s failed: %s", to, subject)
