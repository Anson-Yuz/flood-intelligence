from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from .audit import append_audit
from .config import Settings
from .database import get_db
from .models import AuthSession, User, utcnow


router = APIRouter(prefix="/auth", tags=["auth"])
LOCAL_ENVIRONMENTS = {"development", "dev", "local", "test", "demo"}
DEFAULT_LOCAL_ADMIN_PASSWORD = "Yujian@2026"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    remember: bool = False


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _urlsafe_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def derive_password(password: str, salt: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _urlsafe_decode(salt),
        iterations,
    )
    return _urlsafe_encode(digest)


def create_password_record(password: str, iterations: int) -> tuple[str, str, int]:
    salt = _urlsafe_encode(secrets.token_bytes(16))
    return derive_password(password, salt, iterations), salt, iterations


def verify_password(user: User, password: str) -> bool:
    if not user.password_hash or not user.salt or not user.iterations:
        return False
    candidate = derive_password(password, user.salt, user.iterations)
    return hmac.compare_digest(candidate, user.password_hash)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _settings(request: HTTPConnection) -> Settings:
    return request.app.state.settings


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
        "role": user.role,
        "tenantId": user.tenant_id,
    }


def _auth_response(user: User, session: AuthSession) -> dict[str, Any]:
    return {
        "ok": True,
        "authenticated": True,
        "user": _user_payload(user),
        "expiresAt": _as_utc(session.expires_at).isoformat(),
        "remember": session.remember,
    }


def _cookie_options(settings: Settings) -> dict[str, Any]:
    return {
        "key": settings.auth_cookie_name,
        "path": "/",
        "secure": settings.auth_secure_cookie,
        "httponly": True,
        "samesite": settings.auth_cookie_samesite,
    }


def _set_session_cookie(
    response: Response,
    *,
    token: str,
    session: AuthSession,
    settings: Settings,
) -> None:
    options = _cookie_options(settings)
    max_age = (
        settings.auth_remember_days * 24 * 60 * 60
        if session.remember
        else settings.auth_session_hours * 60 * 60
    )
    response.set_cookie(
        value=token,
        max_age=max_age,
        expires=_as_utc(session.expires_at) if session.remember else None,
        **options,
    )

def _delete_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(**_cookie_options(settings))


def seed_admin_user(db: Session, settings: Settings) -> bool:
    is_local = settings.environment.lower() in LOCAL_ENVIRONMENTS
    password = settings.auth_seed_admin_password
    if password is None and is_local:
        password = settings.auth_local_default_password
    if not password or (not is_local and hmac.compare_digest(password, DEFAULT_LOCAL_ADMIN_PASSWORD)):
        return False

    user = db.scalar(
        select(User).where(
            User.tenant_id == settings.auth_default_tenant_id,
            User.username == settings.auth_seed_admin_username,
        )
    )
    created = False
    if user is None:
        user = User(
            tenant_id=settings.auth_default_tenant_id,
            username=settings.auth_seed_admin_username,
            display_name=settings.auth_seed_admin_display_name,
            role=settings.auth_seed_admin_role,
            region_scope=["*"],
            is_active=True,
        )
        db.add(user)
        created = True

    if not user.password_hash or not user.salt or not user.iterations:
        password_hash, salt, iterations = create_password_record(
            password,
            settings.auth_pbkdf2_iterations,
        )
        user.password_hash = password_hash
        user.salt = salt
        user.iterations = iterations
        db.commit()
        return True
    if created:
        db.commit()
    return created


def resolve_session(
    request: HTTPConnection,
    db: Session,
    *,
    required: bool,
    touch: bool = False,
) -> tuple[User, AuthSession] | None:
    settings = _settings(request)
    raw_token = request.cookies.get(settings.auth_cookie_name)
    if not raw_token:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
        return None

    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_session_token(raw_token))
    )
    now = utcnow()
    if session is None or session.revoked_at is not None:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已过期或已注销")
        return None
    if _as_utc(session.expires_at) <= now:
        session.revoked_at = now
        db.commit()
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已过期或已注销")
        return None

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        session.revoked_at = now
        db.commit()
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已过期或已注销")
        return None

    if touch:
        session.last_seen_at = now
        db.commit()
    return user, session


def get_optional_session_user(request: Request, db: Session) -> User | None:
    resolved = resolve_session(request, db, required=False)
    return resolved[0] if resolved else None


def require_session_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Require a valid operator session for protected application routes."""
    user, _ = resolve_session(request, db, required=True)
    return user


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    username = body.username.strip()
    user = db.scalar(
        select(User).where(
            User.tenant_id == settings.auth_default_tenant_id,
            User.username == username,
        )
    )
    if user is None:
        # Keep the missing-user path computationally comparable to a real password check.
        dummy_salt = _urlsafe_encode(b"yujian-auth-dummy")
        derive_password(body.password, dummy_salt, settings.auth_pbkdf2_iterations)
    if user is None or not user.is_active or not verify_password(user, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    now = utcnow()
    lifetime = (
        timedelta(days=settings.auth_remember_days)
        if body.remember
        else timedelta(hours=settings.auth_session_hours)
    )
    raw_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(
        id=uuid4().hex,
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + lifetime,
        remember=body.remember,
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        ip_address=request.client.host if request.client else None,
    )
    db.add(auth_session)
    append_audit(
        db,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        actor_type="user",
        actor_id=user.display_name,
        trace_id=f"auth-{auth_session.id[:16]}",
        detail={"username": user.username, "remember": body.remember},
        occurred_at=now,
    )
    db.commit()
    _set_session_cookie(response, token=raw_token, session=auth_session, settings=settings)
    return _auth_response(user, auth_session)


@router.get("/session")
def session_state(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    resolved = resolve_session(request, db, required=False, touch=True)
    if not resolved:
        return {"ok": True, "authenticated": False, "user": None}
    user, auth_session = resolved
    return _auth_response(user, auth_session)


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    user, auth_session = resolve_session(request, db, required=True, touch=True)
    return _auth_response(user, auth_session)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = _settings(request)
    resolved = resolve_session(request, db, required=False)
    now = utcnow()
    if resolved:
        user, auth_session = resolved
        auth_session.revoked_at = now
        append_audit(
            db,
            action="auth.logout",
            resource_type="user",
            resource_id=str(user.id),
            actor_type="user",
            actor_id=user.display_name,
            trace_id=f"auth-{auth_session.id[:16]}",
            detail={"sessionId": auth_session.id},
            occurred_at=now,
        )
        db.commit()
    _delete_session_cookie(response, settings)
    return {"ok": True, "authenticated": False}
