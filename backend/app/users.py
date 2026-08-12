"""Users module."""

import hashlib
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app import config
from app.db import get_session
from app.email_utils import send_email
from app.rate_limit import limiter
from shared.scores import Score
from shared.user import User

PASSWORD_RESET_PURPOSE = "password_reset"

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)
if not os.getenv("JWT_SECRET_KEY"):
    logger.warning(
        "JWT_SECRET_KEY is not set; using a random ephemeral secret. "
        "All tokens are invalidated on restart — set JWT_SECRET_KEY in production."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 1


router = APIRouter(prefix="", tags=["users"])


class Token(BaseModel):
    """Token model."""

    access_token: str
    token_type: str


class UserCreate(BaseModel):
    """Public registration body.

    Server-owned fields (``role``, ``credits``, ``max_credits``) are
    deliberately absent so clients cannot self-grant privileges.
    """

    username: str
    password: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    instrument: str | None = None


class UserResponse(BaseModel):
    """User data safe to return to clients — excludes the password hash."""

    id: int
    username: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    instrument: str | None = None
    role: str
    credits: int
    max_credits: int
    last_login: datetime | None = None


class UserAdminResponse(UserResponse):
    """Admin ``GET /users`` row — adds the denormalized score count."""

    score_count: int = 0


class UserUpdateRequest(BaseModel):
    """User update request model."""

    instrument: str | None = None
    email: str | None = None


class PasswordChangeRequest(BaseModel):
    """Password change request model."""

    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request model."""

    email: str


class ResetPasswordRequest(BaseModel):
    """Reset password request model."""

    token: str
    new_password: str


class CreditUpdateRequest(BaseModel):
    """Credit update request model."""

    max_credits: int


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
    session: Session = Depends(get_session),
) -> Token:
    """Login for access token."""
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

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),
):
    """Get current user."""
    return get_current_user_from_token(token, session)


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
    user = get_user(username=username, session=session)
    if user is None:
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


@router.post("/users", response_model=UserResponse)
@limiter.limit("5/minute")
def add_user(
    request: Request,
    user: UserCreate,
    session: Session = Depends(get_session),
):
    """Add a user to the db."""
    if get_user(user.username, session) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    db_user = User(
        username=user.username,
        password=get_password_hash(user.password),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        instrument=user.instrument,
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
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
):
    """Get current user."""
    return current_user


@router.put("/user", response_model=UserResponse)
def update_user(
    req: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Update current user."""
    updated = False
    if req.instrument is not None:
        current_user.instrument = req.instrument
        updated = True

    if req.email is not None:
        current_user.email = req.email
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
    return {"message": "Password updated successfully"}


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    req: ForgotPasswordRequest,
    session: Session = Depends(get_session),
):
    """Email a password reset link if the address belongs to an account.

    Always returns the same generic message so the endpoint can't be used to
    enumerate registered emails.
    """
    user = session.exec(select(User).where(User.email == req.email)).first()
    if user is not None:
        reset_link = (
            f"{config.FRONTEND_URL}/reset-password?token={create_password_reset_token(user)}"
        )
        send_email(
            to=req.email,
            subject="Reset your ScoreGuide password",
            body=(
                f"Hi {user.username},\n\n"
                "We received a request to reset your ScoreGuide password. "
                "Click the link below to choose a new one "
                f"(valid for {config.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n\n"
                f"{reset_link}\n\n"
                "If you didn't request this, you can safely ignore this email."
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


@router.put("/users/{user_id}/credits", response_model=UserResponse)
def set_user_credits(
    user_id: int,
    request: CreditUpdateRequest,
    _: Annotated[User, Depends(get_admin_user)],
    session: Session = Depends(get_session),
):
    """Set max credits for a user (admin only)."""
    user_to_update = session.get(User, user_id)
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")

    user_to_update.max_credits = request.max_credits
    session.add(user_to_update)
    session.commit()
    session.refresh(user_to_update)
    return user_to_update


@router.post("/users/{user_id}/refill_credits", response_model=UserResponse)
def refill_user_credits(
    user_id: int,
    _: Annotated[User, Depends(get_admin_user)],
    session: Session = Depends(get_session),
):
    """Refill credits for a user to their max value (admin only)."""
    user_to_update = session.get(User, user_id)
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")

    user_to_update.credits = user_to_update.max_credits
    session.add(user_to_update)
    session.commit()
    session.refresh(user_to_update)
    return user_to_update


@router.delete("/user")
def delete_account(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Delete current user."""
    session.delete(current_user)
    session.commit()
    return {"message": "Account deleted successfully"}
