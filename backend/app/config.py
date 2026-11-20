"""Centralized backend configuration read from environment variables.

Values are read at import time. Tests that need to override them should patch
the module attribute (``monkeypatch.setattr(config, "NAME", ...)``) rather
than the env var, since we don't re-read the environment on every access.

The per-request ``MODEL`` lookup still lives inline in the handlers because
tests monkeypatch the ``MODEL`` env var at call-time.
"""

import os

MCP_URL = os.getenv("MCP_URL", "http://mcp-postgres:8001/sse")
AGENT_RATE_LIMIT = os.getenv("AGENT_RATE_LIMIT", "5/minute")
MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "50"))
# Storage abuse limits for one account: PDF uploads, and scores in a library.
UPLOAD_RATE_LIMIT = os.getenv("UPLOAD_RATE_LIMIT", "30/hour")
MAX_SCORES_PER_USER = int(os.getenv("MAX_SCORES_PER_USER", "1000"))
# Cost caps for one AI request (one credit): the length of each model answer,
# the number of model calls in one run (tool round-trips, retries) and the
# total tokens spent. A run that hits a cap stops instead of running up the bill.
AI_MAX_OUTPUT_TOKENS = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "8192"))
AI_REQUEST_LIMIT = int(os.getenv("AI_REQUEST_LIMIT", "15"))
AI_TOTAL_TOKENS_LIMIT = int(os.getenv("AI_TOTAL_TOKENS_LIMIT", "300000"))
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "alexis.arnaudon@gmail.com")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

# Used to build the link inside password-reset emails.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))

# SMTP is opt-in: if SMTP_HOST isn't set, send_email() logs instead of sending
# (dev / test / CI), same pattern as Sentry below.
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT") or "587")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SUPPORT_EMAIL)

# New accounts must confirm their email before spending AI credits or
# uploading. On by default only when emails can actually be sent, so a
# deployment without SMTP never locks its users out.
EMAIL_VERIFICATION = os.getenv("EMAIL_VERIFICATION", "1" if SMTP_HOST else "0") == "1"
EMAIL_VERIFY_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFY_EXPIRE_HOURS", "48"))

# Public read-only demo: POST /demo-login issues a token for this account
# (no password). It only works once the account exists with role "demo" —
# create it with ``python -m app.demo <score_id> ...``. Empty disables it.
DEMO_USERNAME = os.getenv("DEMO_USERNAME", "demo")

# Sentry is opt-in: if SENTRY_DSN isn't set, sentry_sdk.init() is skipped entirely.
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "production")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
