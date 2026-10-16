"""Seed load + biomarker count."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.catalog.seed_loader import load_seed_files, seed_catalog
from app.db.session import Base
from app.models import entities as _entities  # noqa: F401
from app.models.entities import Biomarker, BuiltinReferenceRange, UnitConversion

SEED_DIR = Path(__file__).resolve().parents[2] / "app" / "catalog" / "seed"


def test_seed_json_count():
    data = json.loads((SEED_DIR / "biomarkers.json").read_text(encoding="utf-8"))
    assert len(data) >= 150
    keys = [d["canonical_key"] for d in data]
    assert len(keys) == len(set(keys))
    # Required categories present
    cats = {d["category"] for d in data}
    for required in (
        "cbc",
        "lipids",
        "liver",
        "kidney",
        "thyroid",
        "diabetes",
        "vitamins_iron",
        "hormones",
        "inflammation_cardiac",
        "coagulation",
        "urine",
        "tumor_markers",
    ):
        assert required in cats


def test_seed_loads_into_db(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        counts = seed_catalog(db)
        assert counts["biomarkers_total"] >= 150
        assert counts["conversions"] > 0
        assert counts["builtin_ranges"] > 0
        n = db.scalar(select(Biomarker).count()) if False else len(db.scalars(select(Biomarker)).all())
        assert n >= 150
        assert len(db.scalars(select(UnitConversion)).all()) > 0
        assert len(db.scalars(select(BuiltinReferenceRange)).all()) > 0
        # Idempotent second load
        counts2 = seed_catalog(db)
        assert counts2["biomarkers_total"] == counts["biomarkers_total"]
        assert len(db.scalars(select(Biomarker)).all()) == n
    finally:
        db.close()


def test_load_seed_files_keys():
    data = load_seed_files()
    assert "biomarkers" in data and "conversions" in data and "builtin_ranges" in data
