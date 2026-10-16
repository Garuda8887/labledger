"""Consistent API error format."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_body(
    detail: str,
    *,
    code: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": detail}
    if code:
        body["code"] = code
    if errors:
        body["errors"] = errors
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        code = None
        if isinstance(detail, dict):
            code = detail.get("code")
            detail = detail.get("detail", str(detail))
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(str(detail), code=code),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exc_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            errors.append(
                {
                    "loc": [str(x) for x in err.get("loc", [])],
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=422,
            content=error_body("Validation failed", code="validation_error", errors=errors),
        )
