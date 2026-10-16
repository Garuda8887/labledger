from __future__ import annotations

from pathlib import Path

import pytest

from app.extraction.pipeline import process_document, process_file

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "extraction"


def test_process_file_digital_pdf_pending_rows():
    result = process_file(FIXTURES / "northvale_cbc_lipid.pdf")
    assert result.status == "needs_review"
    assert result.rows_extracted >= 5
    assert result.page_count == 1
    assert result.source_type == "digital_pdf"
    assert any(c.raw_test_name for c in result.candidates)
    assert all(c.status == "pending_review" for c in result.candidates)
    # Prefer real catalog match when C is present
    names = [c.raw_test_name.lower() for c in result.candidates]
    assert any("hemoglobin" in n for n in names)


def test_process_document_persists(tmp_path, monkeypatch):
    from app.core import config
    from app.db.session import SessionLocal, init_db
    from app.extraction.ingest import store_path
    from app.models.entities import Document, Profile, Result

    monkeypatch.setattr(config.settings, "labledger_data_dir", tmp_path)
    # Re-bind engine to temp DB
    import app.db.session as sess

    monkeypatch.setattr(sess.settings, "labledger_data_dir", tmp_path)
    # recreate engine for temp path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "labledger.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    sess.Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(sess, "engine", engine)
    monkeypatch.setattr(sess, "SessionLocal", TestSession)

    db = TestSession()
    try:
        profile = Profile(display_name="Fixture Person")
        db.add(profile)
        db.commit()
        db.refresh(profile)
        ingested = store_path(profile.id, FIXTURES / "northvale_cbc_lipid.pdf")
        doc = Document(
            profile_id=profile.id,
            original_filename=ingested.original_filename,
            sha256=ingested.sha256,
            mime=ingested.mime,
            stored_path=ingested.stored_path,
            source_type="digital_pdf",
            status="processing",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        result = process_document(doc.id, session=db)
        assert result.status == "needs_review"
        assert result.rows_persisted >= 5
        db.refresh(doc)
        assert doc.status == "needs_review"
        assert doc.lab_name is not None
        rows = db.query(Result).filter(Result.document_id == doc.id).all()
        assert len(rows) >= 5
        assert all(r.status == "pending_review" for r in rows)
    finally:
        db.close()


def test_plugin_off_by_default(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_PLUGIN", raising=False)
    from app.extraction.plugins import get_extractor_plugin

    assert get_extractor_plugin(None) is None
    assert get_extractor_plugin("") is None


def test_paddle_stub_raises():
    from app.extraction.ocr import get_ocr_adapter
    import numpy as np

    adapter = get_ocr_adapter("paddle")
    with pytest.raises(RuntimeError, match="PaddleOCR"):
        adapter.extract_words(np.zeros((10, 10, 3), dtype=np.uint8))
