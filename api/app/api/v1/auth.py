"""Optional app lock via APP_PASSPHRASE."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.core import auth as auth_mod
from app.core.config import settings
from app.schemas.common import AuthStatusResponse, MessageResponse, UnlockRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(request: Request) -> AuthStatusResponse:
    locked = settings.passphrase_enabled
    unlocked = (not locked) or auth_mod.verify_session_cookie(
        request.cookies.get(auth_mod.COOKIE_NAME)
    )
    return AuthStatusResponse(locked=locked, unlocked=unlocked)


@router.post("/unlock", response_model=MessageResponse)
def unlock(body: UnlockRequest, request: Request, response: Response) -> MessageResponse:
    if not settings.passphrase_enabled:
        return MessageResponse(message="Lock disabled")
    if not auth_mod.check_passphrase(body.passphrase):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail={"detail": "Invalid passphrase", "code": "invalid_passphrase"},
        )
    auth_mod.set_session_cookie(response, request, body.passphrase)
    return MessageResponse(message="Unlocked")


@router.post("/lock", response_model=MessageResponse)
def lock(response: Response) -> MessageResponse:
    auth_mod.clear_session_cookie(response)
    return MessageResponse(message="Locked")
