"""Tests for app.email_utils."""

from unittest.mock import MagicMock

from app import config, email_utils


def test_send_email_not_configured(monkeypatch):
    """send_email is a no-op (logs) when SMTP_HOST isn't set."""
    monkeypatch.setattr(config, "SMTP_HOST", None)
    email_utils.send_email("to@example.com", "subject", "body")


def test_send_email_sends_via_smtp(monkeypatch):
    """send_email opens an SMTP connection, authenticates, and sends the message."""
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    monkeypatch.setattr(config, "SMTP_USER", "user")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "pass")
    monkeypatch.setattr(config, "SMTP_FROM", "noreply@example.com")

    smtp_cls = MagicMock()
    smtp_instance = smtp_cls.return_value.__enter__.return_value
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    email_utils.send_email("to@example.com", "subject", "body")

    smtp_cls.assert_called_once_with("smtp.example.com", 587)
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("user", "pass")
    smtp_instance.send_message.assert_called_once()
    sent_message = smtp_instance.send_message.call_args[0][0]
    assert sent_message["To"] == "to@example.com"
    assert sent_message["From"] == "noreply@example.com"
    assert sent_message["Subject"] == "subject"


def test_send_email_without_smtp_user_skips_login(monkeypatch):
    """No SMTP_USER configured means login() isn't called (anonymous relay)."""
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_USER", None)

    smtp_cls = MagicMock()
    smtp_instance = smtp_cls.return_value.__enter__.return_value
    monkeypatch.setattr(email_utils.smtplib, "SMTP", smtp_cls)

    email_utils.send_email("to@example.com", "subject", "body")

    smtp_instance.login.assert_not_called()
    smtp_instance.send_message.assert_called_once()
