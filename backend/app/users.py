"""Users module."""

import hashlib
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app import config
from app.db import get_session
from app.email_utils import send_email_safely
from app.rate_limit import limiter
from shared.scores import Score
from shared.usage import UsageSummary
from shared.user import User

PASSWORD_RESET_PURPOSE = "password_reset"
EMAIL_VERIFY_PURPOSE = "verify_email"
DEMO_ROLE = "demo"
# The demo account may browse, never change anything.
READ_ONLY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

logger = logging.getLogger(__name__)


def _secret_key() -> str:
    """JWT signing key: required in production, random (per process) elsewhere."""
    key = os.getenv("JWT_SECRET_KEY", "")
    if key:
        return key
    if config.APP_ENV == "production":
        raise RuntimeError("JWT_SECRET_KEY must be set in production (APP_ENV=production)")
    logger.warning(
        "JWT_SECRET_KEY is not set; using a random ephemeral secret. "
        "All tokens are invalidated on restart — set JWT_SECRET_KEY in production."
    )
    return secrets.token_hex(32)


SECRET_KEY = _secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 1
# "Keep me logged in" — must match the cookie maxAge set by the Svelte login action.
REMEMBER_ME_EXPIRE_MINUTES = 60 * 24 * 30


router = APIRouter(prefix="", tags=["users"])


class Token(BaseModel):
    """Token model."""

    access_token: str
    token_type: str


# Minimum length is the one rule that measurably helps (NIST 800-63B); the
# cap keeps a megabyte "password" from being hashed on every login attempt.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
Password = Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]


# The free-text "about your music" field: long enough for a few sentences,
# short enough to add to every assistant prompt.
MUSIC_PROFILE_MAX_LENGTH = 1000


class UserCreate(BaseModel):
    """Public registration body.

    Server-owned fields (``role``, ``plan``, allowances) are
    deliberately absent so clients cannot self-grant privileges.
    """

    username: str = Field(min_length=1, max_length=50)
    password: Password
    email: EmailStr
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    instrument: str | None = Field(default=None, max_length=50)
    music_profile: str | None = Field(default=None, max_length=MUSIC_PROFILE_MAX_LENGTH)


class UserResponse(BaseModel):
    """User data safe to return to clients — excludes the password hash."""

    id: int
    username: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    instrument: str | None = None
    music_profile: str | None = None
    detailed_descriptions: bool = False
    role: str
    plan: str = "free"
    last_login: datetime | None = None
    email_verified: bool = True
    # Plan limits and this month's use; only filled by ``GET /user``.
    usage: UsageSummary | None = None


class UserAdminResponse(UserResponse):
    """Admin ``GET /users`` row — adds the score count and limit overrides."""

    score_count: int = 0
    ai_allowance: int | None = None
    storage_limit_mb: int | None = None


class UserUpdateRequest(BaseModel):
    """User update request model."""

    instrument: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    music_profile: str | None = Field(default=None, max_length=MUSIC_PROFILE_MAX_LENGTH)
    detailed_descriptions: bool | None = None


class PasswordChangeRequest(BaseModel):
    """Password change request model."""

    current_password: str
    new_password: Password


class ForgotPasswordRequest(BaseModel):
    """Forgot password request model."""

    email: str = Field(max_length=254)


class VerifyEmailRequest(BaseModel):
    """Token from the link in the verification email."""

    token: str


class ResetPasswordRequest(BaseModel):
    """Reset password request model."""

    token: str
    new_password: Password


password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    """Verify password."""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Get password hash."""
    return password_hash.hash(password)


def get_user(username: str, session: Session):
    """Get user by username."""
    return session.exec(select(User).where(User.username == username)).first()


def username_taken(username: str, session: Session) -> bool:
    """Whether an account already has this name, ignoring case ("Bob" = "bob")."""
    return (
        session.exec(select(User).where(func.lower(User.username) == username.lower())).first()
        is not None
    )


# Verified against when the username doesn't exist, so unknown-user and
# wrong-password attempts take the same time (no user enumeration via timing).
_DUMMY_PASSWORD_HASH = password_hash.hash("dummy-password")


def authenticate_user(username: str, password: str, session: Session):
    """Authenticate user."""
    user = get_user(username, session)
    if not user or not user.password:
        password_hash.verify(password, _DUMMY_PASSWORD_HASH)
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def _password_fingerprint(user: User) -> str:
    """Short digest of the user's current password hash.

    Embedded in reset tokens so that resetting the password (or changing it
    in the meantime) invalidates any outstanding token — no server-side
    token storage needed.
    """
    return hashlib.sha256((user.password or "").encode()).hexdigest()[:16]


def create_session_token(user: User, expires_delta: timedelta) -> str:
    """A login token. It carries the password fingerprint, so changing or
    resetting the password signs out every other session."""
    return create_access_token(
        data={"sub": user.username, "role": user.role, "pwd_fp": _password_fingerprint(user)},
        expires_delta=expires_delta,
    )


def create_email_verification_token(user: User) -> str:
    """Token for the "confirm your email" link, bound to the current address."""
    return create_access_token(
        data={"sub": user.username, "purpose": EMAIL_VERIFY_PURPOSE, "email": user.email},
        expires_delta=timedelta(hours=config.EMAIL_VERIFY_EXPIRE_HOURS),
    )


def send_verification_email(user: User, background_tasks: BackgroundTasks) -> None:
    """Email the confirmation link (in the background: SMTP can be slow)."""
    if not user.email:  # pragma: no cover - callers check
        return
    link = f"{config.FRONTEND_URL}/verify-email?token={create_email_verification_token(user)}"
    background_tasks.add_task(
        send_email_safely,
        user.email,
        "Confirm your ScoreGuide email / Confirmez votre e-mail ScoreGuide",
        (
            f"Hi {user.username},\n\n"
            "Please confirm your email address to finish setting up your ScoreGuide "
            "account:\n\n"
            f"{link}\n\n"
            "---\n\n"
            f"Bonjour {user.username},\n\n"
            "Merci de confirmer votre adresse e-mail pour terminer la création de votre "
            "compte ScoreGuide :\n\n"
            f"{link}\n\n"
            "If you didn't create this account, ignore this email. / "
            "Si vous n'avez pas créé ce compte, ignorez cet e-mail."
        ),
    )


def email_taken(email: str, session: Session, exclude_user_id: int | None = None) -> bool:
    """Whether another account already uses this address (case-insensitive)."""
    query = select(User).where(func.lower(User.email) == email.lower())
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    return session.exec(query).first() is not None


def create_password_reset_token(user: User) -> str:
    """Create a short-lived, single-use password reset token."""
    return create_access_token(
        data={
            "sub": user.username,
            "purpose": PASSWORD_RESET_PURPOSE,
            "pwd_fp": _password_fingerprint(user),
        },
        expires_delta=timedelta(minutes=config.PASSWORD_RESET_EXPIRE_MINUTES),
    )


@router.post("/token")
@limiter.limit("10/minute")
def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    remember: Annotated[bool, Form()] = False,
    session: Session = Depends(get_session),
) -> Token:
    """Login for access token.

    With ``remember=true`` the token lives 30 days instead of 1 day.
    """
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login = datetime.now(UTC)
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token_expires = timedelta(
        minutes=REMEMBER_ME_EXPIRE_MINUTES if remember else ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_session_token(user, access_token_expires)
    return Token(access_token=access_token, token_type="bearer")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),
    *,
    request: Request,
):
    """Get current user.

    The demo account is read-only: it is rejected on every write request,
    which covers all score/annotation/account mutations and the paid agent
    endpoints in one place.
    """
    user = get_current_user_from_token(token, session)
    if user.role == DEMO_ROLE and request.method not in READ_ONLY_METHODS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The demo account is read-only. Create a free account to do this.",
        )
    return user


@router.post("/demo-login")
# Per visitor IP (forwarded by the SvelteKit proxy). Minting a token is cheap.
@limiter.limit("60/minute")
def demo_login(request: Request, session: Session = Depends(get_session)) -> Token:
    """Issue a token for the read-only demo account, no password needed.

    Only works when ``DEMO_USERNAME`` names an existing user with role
    ``demo`` — a regular or admin account can never be reached this way.
    """
    user = get_user(config.DEMO_USERNAME, session) if config.DEMO_USERNAME else None
    if user is None or user.role != DEMO_ROLE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo not available")
    access_token = create_session_token(user, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return Token(access_token=access_token, token_type="bearer")


def get_current_user_from_token(token: str, session: Session):
    """Validate a token and return the corresponding user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError as exc:
        raise credentials_exception from exc
    # Single-purpose tokens (password reset links) are never sessions.
    if payload.get("purpose") is not None:
        raise credentials_exception
    user = get_user(username=username, session=session)
    if user is None:
        raise credentials_exception
    # Signed out by a password change. Tokens issued before fingerprints were
    # added have none; they expire on their own within REMEMBER_ME days.
    fingerprint = payload.get("pwd_fp")
    if fingerprint is not None and fingerprint != _password_fingerprint(user):
        raise credentials_exception
    return user


def get_admin_user(user: User = Depends(get_current_user)):
    """Get admin user only; raises 403 for everyone else.

    Must raise (not return None): FastAPI treats any returned value —
    including None — as a passing dependency, so a non-raising version
    would let regular users through ``dependencies=[Depends(...)]`` guards.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to perform this action.",
        )
    return user


def get_verified_user(user: User = Depends(get_current_user)):
    """The current user, once their email is confirmed (when verification is on).

    Guards what costs money or storage — AI credits, uploads — so throwaway
    accounts can't farm free credits.
    """
    if config.EMAIL_VERIFICATION and not user.email_verified and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please confirm your email address first (check your inbox).",
        )
    return user


@router.post("/verify-email")
@limiter.limit("10/minute")
def verify_email(
    request: Request, req: VerifyEmailRequest, session: Session = Depends(get_session)
):
    """Confirm an email address from the emailed link (no login needed)."""
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired confirmation link"
    )
    try:
        payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise invalid from exc
    username = payload.get("sub")
    user = get_user(username, session) if username else None
    # Bound to the address it was sent to: changing email voids old links.
    if (
        payload.get("purpose") != EMAIL_VERIFY_PURPOSE
        or user is None
        or not user.email
        or payload.get("email") != user.email
    ):
        raise invalid
    user.email_verified = True
    session.add(user)
    session.commit()
    return {"message": "Email confirmed"}


@router.post("/resend-verification")
@limiter.limit("3/hour")
def resend_verification(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
):
    """Send the confirmation link again."""
    if current_user.email_verified or not current_user.email:
        return {"message": "Nothing to confirm"}
    send_verification_email(current_user, background_tasks)
    return {"message": "Confirmation email sent"}


@router.post("/users", response_model=UserResponse)
@limiter.limit("5/minute")
def add_user(
    request: Request,
    user: UserCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Add a user to the db and email them a confirmation link."""
    if username_taken(user.username, session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    if email_taken(user.email, session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An account already uses this email"
        )
    db_user = User(
        username=user.username,
        password=get_password_hash(user.password),
        email=user.email.lower(),
        first_name=user.first_name,
        last_name=user.last_name,
        instrument=user.instrument,
        music_profile=(user.music_profile or "").strip() or None,
        email_verified=not config.EMAIL_VERIFICATION,
    )
    session.add(db_user)
    try:
        session.commit()
    except IntegrityError as exc:
        # Two sign-ups for the same name or email at once: the unique indexes
        # stop the second one, which gets the same answer as a checked clash.
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username or email already taken"
        ) from exc
    session.refresh(db_user)
    if config.EMAIL_VERIFICATION:
        send_verification_email(db_user, background_tasks)
    return db_user


@router.get("/users", response_model=list[UserAdminResponse])
def get_users(_: Annotated[User, Depends(get_admin_user)], session: Session = Depends(get_session)):
    """Get all users from the db."""
    users = session.exec(select(User)).all()
    result = []
    for user in users:
        count = session.exec(select(func.count(Score.id)).where(Score.user_id == user.id)).one()
        user_dict = user.model_dump()
        user_dict["score_count"] = count
        result.append(user_dict)
    return result


@router.get("/user", response_model=UserResponse)
def get_current_user_route(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Get current user, with their plan's limits and this month's use."""
    from app.plans import usage_summary  # app.plans imports this module

    response = UserResponse.model_validate(current_user, from_attributes=True)
    response.usage = usage_summary(current_user, session)
    return response


@router.put("/user", response_model=UserResponse)
def update_user(
    req: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Update current user. A new email address must be confirmed again."""
    updated = False
    if req.instrument is not None:
        current_user.instrument = req.instrument
        updated = True
    if req.music_profile is not None:
        current_user.music_profile = req.music_profile.strip() or None
        updated = True
    if req.detailed_descriptions is not None:
        current_user.detailed_descriptions = req.detailed_descriptions
        updated = True

    new_email = req.email.lower() if req.email is not None else None
    if new_email is not None and new_email != (current_user.email or "").lower():
        if email_taken(new_email, session, exclude_user_id=current_user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="An account already uses this email"
            )
        current_user.email = new_email
        if config.EMAIL_VERIFICATION:
            current_user.email_verified = False
            send_verification_email(current_user, background_tasks)
        updated = True

    if updated:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    return current_user


@router.get("/is_admin")
def is_admin(current_user: Annotated[User, Depends(get_current_user)]):
    """Check if user is admin."""
    return current_user.role == "admin"


@router.put("/user/password")
def update_password(
    req: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Update user password."""
    if not verify_password(req.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )
    current_user.password = get_password_hash(req.new_password)
    session.add(current_user)
    session.commit()
    # Other sessions are now invalid; hand this one a fresh token.
    return {
        "message": "Password updated successfully",
        "access_token": create_session_token(
            current_user, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        ),
    }


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    req: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Email a password reset link if the address belongs to an account.

    Always returns the same generic message so the endpoint can't be used to
    enumerate registered emails.
    """
    user = session.exec(select(User).where(func.lower(User.email) == req.email.lower())).first()
    if user is not None and user.email:
        reset_link = (
            f"{config.FRONTEND_URL}/reset-password?token={create_password_reset_token(user)}"
        )
        background_tasks.add_task(
            send_email_safely,
            user.email,
            "Reset your ScoreGuide password / Réinitialiser votre mot de passe",
            (
                f"Hi {user.username},\n\n"
                "We received a request to reset your ScoreGuide password. "
                "Click the link below to choose a new one "
                f"(valid for {config.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n\n"
                f"{reset_link}\n\n"
                "If you didn't request this, you can safely ignore this email.\n\n"
                "---\n\n"
                f"Bonjour {user.username},\n\n"
                "Nous avons reçu une demande de réinitialisation de votre mot de passe "
                "ScoreGuide. Choisissez-en un nouveau avec ce lien "
                f"(valable {config.PASSWORD_RESET_EXPIRE_MINUTES} minutes) :\n\n"
                f"{reset_link}\n\n"
                "Si vous n'avez rien demandé, ignorez simplement cet e-mail."
            ),
        )
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    req: ResetPasswordRequest,
    session: Session = Depends(get_session),
):
    """Set a new password from a valid password reset token."""
    invalid_token_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset link",
    )
    try:
        payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise invalid_token_exception from exc

    username = payload.get("sub")
    user = get_user(username, session) if username else None
    if (
        payload.get("purpose") != PASSWORD_RESET_PURPOSE
        or user is None
        or payload.get("pwd_fp") != _password_fingerprint(user)
    ):
        raise invalid_token_exception

    user.password = get_password_hash(req.new_password)
    session.add(user)
    session.commit()
    return {"message": "Password reset successfully"}
