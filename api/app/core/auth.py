"""Optional APP_PASSPHRASE session-cookie lock (default off)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Callable

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings

COOKIE_NAME = "labledger_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _passphrase_digest(passphrase: str) -> str:
    return hashlib.sha256(passphrase.encode("utf-8")).hexdigest()


def _sign(payload: str) -> str:
    key = settings.signing_key().encode("utf-8")
    sig = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _unsign(token: str, max_age: int = MAX_AGE_SECONDS) -> str | None:
    if "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    key = settings.signing_key().encode("utf-8")
    expected = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        ph, ts_s = payload.split(":", 1)
        ts = int(ts_s)
    except ValueError:
        return None
    if abs(int(time.time()) - ts) > max_age:
        return None
    return ph


def _token_for_passphrase(passphrase: str) -> str:
    ph = _passphrase_digest(passphrase)[:16]
    payload = f"{ph}:{int(time.time())}"
    return _sign(payload)


def verify_session_cookie(cookie_value: str | None) -> bool:
    if not settings.passphrase_enabled:
        return True
    if not cookie_value:
        return False
    ph = _unsign(cookie_value)
    if ph is None:
        return False
    expected = _passphrase_digest(settings.app_passphrase or "")[:16]
    return hmac.compare_digest(ph, expected)


def _is_https(request: Request) -> bool:
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto.split(",")[0].strip().lower() == "https"


def set_session_cookie(response: Response, request: Request, passphrase: str) -> None:
    token = _token_for_passphrase(passphrase)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_is_https(request),
        samesite="lax",
        max_age=MAX_AGE_SECONDS,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def check_passphrase(passphrase: str) -> bool:
    if not settings.app_passphrase:
        return True
    return secrets.compare_digest(passphrase, settings.app_passphrase)


async def require_unlocked(request: Request) -> None:
    """Dependency: when APP_PASSPHRASE is set, require a valid session cookie."""
    if not settings.passphrase_enabled:
        return
    path = request.url.path
    if path in ("/api/v1/auth/unlock", "/api/v1/auth/status", "/api/v1/health") or path == "/":
        return
    cookie = request.cookies.get(COOKIE_NAME)
    if not verify_session_cookie(cookie):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "App is locked", "code": "app_locked"},
        )


def unlocked_dependency() -> Callable:
    return require_unlocked
