"""Labledger FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging_utils import log_event
from app.services.jobs import start_worker, stop_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.labledger_data_dir.mkdir(parents=True, exist_ok=True)
    (settings.files_dir).mkdir(parents=True, exist_ok=True)
    (settings.backups_dir).mkdir(parents=True, exist_ok=True)
    start_worker()
    log_event("app_started", bind_host=settings.bind_host)
    try:
        yield
    finally:
        stop_worker()
        log_event("app_stopped")


app = FastAPI(
    title="Labledger API",
    version=__version__,
    description=(
        "Longitudinal pathology-report API. Informational only — not medical advice. "
        "Local-first; verify before commit."
    ),
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "labledger", "version": __version__, "docs": "/docs"}
