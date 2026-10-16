from __future__ import annotations

from pathlib import Path

import pytest

from app.extraction.ingest import IngestError, compute_sha256, store_bytes, store_path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "extraction"


def test_sha256_stable():
    assert compute_sha256(b"abc") == compute_sha256(b"abc")
    assert compute_sha256(b"abc") != compute_sha256(b"abd")


def test_store_pdf_dedupe(tmp_path, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "labledger_data_dir", tmp_path)
    pdf = FIXTURES / "northvale_cbc_lipid.pdf"
    data = pdf.read_bytes()
    r1 = store_bytes("prof-1", data, "northvale.pdf")
    r2 = store_bytes("prof-1", data, "northvale-copy.pdf")
    assert r1.sha256 == r2.sha256
    assert r1.deduplicated is False
    assert r2.deduplicated is True
    assert (tmp_path / r1.stored_path).exists()
    assert r1.mime == "application/pdf"


def test_reject_bad_extension(tmp_path, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "labledger_data_dir", tmp_path)
    with pytest.raises(IngestError):
        store_bytes("prof-1", b"%PDF-1.4", "report.exe")


def test_store_path(tmp_path, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "labledger_data_dir", tmp_path)
    r = store_path("prof-2", FIXTURES / "northvale_page1.png")
    assert r.mime == "image/png"
    assert (tmp_path / r.stored_path).exists()
