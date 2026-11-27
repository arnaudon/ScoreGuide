"""AI providers: model strings to pydantic-ai models, with credentials from the admin.

Model strings are pydantic-ai's (``google:gemini-2.5-flash``) plus
``infomaniak:<model>`` for Infomaniak's OpenAI-compatible AI Services
(open models hosted in Switzerland). Credentials are set on the admin page and
stored in ``Setting`` rows; environment variables remain the fallback, so an
existing deployment keeps working until a key is entered.

Keys are write-only through the API: the admin only ever sees whether a key is
set and its last characters.
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from sqlmodel import Session, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.users import get_admin_user
from shared.settings import Setting

# Credential name -> environment variable used when the admin hasn't set one.
CREDENTIALS = {
    "google_api_key": "GOOGLE_API_KEY",
    "infomaniak_api_key": "INFOMANIAK_API_KEY",
    "infomaniak_product_id": "INFOMANIAK_PRODUCT_ID",
}
# Not secret: shown in full on the admin page.
PUBLIC_CREDENTIALS = {"infomaniak_product_id"}
PREFIX = "credential_"
INFOMANIAK_URL = "https://api.infomaniak.com/2/ai/{product_id}/openai/v1"


class MissingCredential(Exception):
    """A model needs a credential that is neither set by the admin nor in env."""


def _resolve(stored: dict[str, str], name: str) -> str:
    return stored.get(name) or os.getenv(CREDENTIALS[name]) or ""


def _require(stored: dict[str, str], name: str) -> str:
    value = _resolve(stored, name)
    if not value:
        raise MissingCredential(f"{name} is not set (admin page or {CREDENTIALS[name]})")
    return value


def build_model(name: str, stored: dict[str, str]) -> Model | str:
    """A pydantic-ai model for ``name``; other strings ("test", ...) pass through."""
    provider, _, model = name.partition(":")
    if provider in ("google", "google-gla") and model:
        key = _resolve(stored, "google_api_key")
        # Without an admin key, let pydantic-ai read GOOGLE_API_KEY itself.
        return GoogleModel(model, provider=GoogleProvider(api_key=key)) if key else name
    if provider == "infomaniak" and model:
        base_url = INFOMANIAK_URL.format(product_id=_require(stored, "infomaniak_product_id"))
        api_key = _require(stored, "infomaniak_api_key")
        return OpenAIChatModel(model, provider=OpenAIProvider(base_url=base_url, api_key=api_key))
    return name


def _stored_sync(session: Session) -> dict[str, str]:
    rows = session.exec(select(Setting).where(col(Setting.key).startswith(PREFIX)))
    return {r.key.removeprefix(PREFIX): r.value for r in rows}


async def _stored(session: AsyncSession) -> dict[str, str]:
    rows = await session.exec(select(Setting).where(col(Setting.key).startswith(PREFIX)))
    return {r.key.removeprefix(PREFIX): r.value for r in rows}


async def named_agent_model(session: AsyncSession, setting_key: str) -> tuple[str, Model | str]:
    """The configured model's name (for the usage log) and the model, ready to run."""
    setting = await session.get(Setting, setting_key)
    name = setting.value if setting else os.getenv("MODEL", "test")
    return name, build_model(name, await _stored(session))


# --- Admin API ----------------------------------------------------------------

router = APIRouter(prefix="/admin/credentials", tags=["admin"])


class CredentialStatus(BaseModel):
    """What the admin page shows: never the secret itself."""

    set: bool
    source: str  # "admin", "env" or ""
    hint: str


class CredentialsUpdate(BaseModel):
    """New values; an empty string removes the admin value (back to env)."""

    credentials: dict[str, Annotated[str, Field(max_length=500)]]


def _hint(name: str, value: str) -> str:
    if name in PUBLIC_CREDENTIALS:
        return value
    return f"…{value[-4:]}" if len(value) > 8 else "…"


def credential_status(session: Session) -> dict[str, CredentialStatus]:
    """Whether each credential is set, where it comes from, and a short hint."""
    stored = _stored_sync(session)
    status = {}
    for name, env in CREDENTIALS.items():
        value = stored.get(name) or os.getenv(env, "")
        source = "admin" if stored.get(name) else ("env" if value else "")
        status[name] = CredentialStatus(
            set=bool(value), source=source, hint=_hint(name, value) if value else ""
        )
    return status


@router.get("", dependencies=[Depends(get_admin_user)])
def get_credentials(session: Session = Depends(get_session)) -> dict[str, CredentialStatus]:
    """Credential status for the admin page."""
    return credential_status(session)


@router.post("", dependencies=[Depends(get_admin_user)])
def set_credentials(
    body: CredentialsUpdate, session: Session = Depends(get_session)
) -> dict[str, CredentialStatus]:
    """Store (or clear, with "") credentials; unknown names are ignored."""
    for name, value in body.credentials.items():
        if name not in CREDENTIALS:
            continue
        row = session.get(Setting, PREFIX + name)
        value = value.strip()
        if value:
            if row:
                row.value = value
            else:
                row = Setting(key=PREFIX + name, value=value)
            session.add(row)
        elif row:
            session.delete(row)
    session.commit()
    return credential_status(session)


# --- Public: which models answer (privacy page) -------------------------------

public_router = APIRouter(tags=["ai"])

AGENT_SETTINGS = ("model_main", "model_imslp", "model_complete")
# Who runs the model, by provider prefix (None: a test or unknown model).
HOSTS = {"infomaniak": "infomaniak", "google": "google", "google-gla": "google"}


class AIModel(BaseModel):
    """A model in use: ``Kimi-K2.6`` by ``moonshotai``, run by ``infomaniak``."""

    name: str
    vendor: str
    host: str


class AIModels(BaseModel):
    models: list[AIModel]


def describe(name: str) -> AIModel | None:
    """The public description of a model string; None when it isn't a real model."""
    provider, _, model = name.partition(":")
    host = HOSTS.get(provider)
    if not host or not model:
        return None
    vendor, _, short = model.rpartition("/")
    return AIModel(name=short, vendor=vendor or provider.split("-")[0], host=host)


@public_router.get("/ai-models")
def ai_models(session: Session = Depends(get_session)) -> AIModels:
    """The models the assistants use now, without duplicates. Names only: no keys."""
    models: list[AIModel] = []
    for key in AGENT_SETTINGS:
        setting = session.get(Setting, key)
        model = describe(setting.value if setting else os.getenv("MODEL", "test"))
        if model and model not in models:
            models.append(model)
    return AIModels(models=models)
