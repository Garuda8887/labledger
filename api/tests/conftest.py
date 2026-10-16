"""Shared fixtures — isolated temp DB per test, no PHI."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.db import session as db_session
from app.models import Biomarker
from app.services.jobs import run_pending_jobs_once, stop_worker


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "labledger_data_dir", tmp_path)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "app_passphrase", None)
    db_session.configure_engine(settings.sqlalchemy_url)
    db_session.init_db()
    return tmp_path


@pytest.fixture()
def client(data_dir: Path):
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        # Lifespan starts the worker; prefer sync job drains in tests
        stop_worker()
        yield c
    stop_worker()
    run_pending_jobs_once()


@pytest.fixture()
def sample_png_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def two_profiles(client: TestClient):
    a = client.post(
        "/api/v1/profiles",
        json={"display_name": "Person A", "sex": "female", "preferred_unit_system": "conventional"},
    )
    b = client.post(
        "/api/v1/profiles",
        json={"display_name": "Person B", "sex": "male", "preferred_unit_system": "si"},
    )
    assert a.status_code == 201
    assert b.status_code == 201
    return a.json(), b.json()


@pytest.fixture()
def seed_biomarker(data_dir: Path):
    db = db_session.SessionLocal()
    try:
        b = Biomarker(
            canonical_key="hemoglobin",
            display_name="Hemoglobin",
            category="cbc",
            canonical_unit="g/dL",
            decimals=1,
            aliases=["Hb", "HGB", "Haemoglobin"],
            plausibility_min=3.0,
            plausibility_max=25.0,
        )
        db.add(b)
        db.commit()
        db.refresh(b)
        return {"id": b.id, "canonical_key": b.canonical_key, "category": b.category}
    finally:
        db.close()
