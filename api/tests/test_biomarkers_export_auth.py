import io
import zipfile
from pathlib import Path

from app.core.config import settings
from app.services.backups import backup_database, list_backups, prune_backups
from app.services.jobs import run_pending_jobs_once


def test_biomarker_catalog_empty_and_seeded(client, seed_biomarker):
    r = client.get("/api/v1/biomarkers")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    search = client.get("/api/v1/biomarkers", params={"q": "hb"})
    assert search.status_code == 200
    assert search.json()["total"] >= 1

    one = client.get(f"/api/v1/biomarkers/{seed_biomarker["id"]}")
    assert one.status_code == 200
    assert one.json()["canonical_key"] == "hemoglobin"


def test_export_import_profile(client, two_profiles, sample_png_bytes, seed_biomarker):
    a, _ = two_profiles
    up = client.post(
        f"/api/v1/profiles/{a['id']}/documents",
        files={"files": ("lab.png", sample_png_bytes, "image/png")},
    )
    doc = up.json()["documents"][0]
    run_pending_jobs_once()
    client.post(
        "/api/v1/results",
        json={
            "document_id": doc["id"],
            "profile_id": a["id"],
            "raw_test_name": "Hb",
            "raw_value": "12.0",
            "biomarker_id": seed_biomarker["id"],
        },
    )
    client.post(f"/api/v1/results/{client.get('/api/v1/results', params={'profile_id': a['id']}).json()['items'][0]['id']}/confirm")

    exp = client.get(f"/api/v1/profiles/{a['id']}/export")
    assert exp.status_code == 200
    assert exp.headers["content-type"] == "application/zip"
    zdata = exp.content
    assert zipfile.is_zipfile(io.BytesIO(zdata))

    imp = client.post(
        "/api/v1/profiles/import",
        files={"file": ("export.zip", zdata, "application/zip")},
    )
    assert imp.status_code == 200, imp.text
    new_id = imp.json()["id"]
    assert new_id != a["id"]
    docs = client.get(f"/api/v1/profiles/{new_id}/documents").json()
    assert docs["total"] == 1
    results = client.get("/api/v1/results", params={"profile_id": new_id}).json()
    assert results["total"] == 1


def test_backup_helper(data_dir):
    # DB created by fixture
    path = backup_database(keep=14)
    assert path.exists()
    assert path.parent == settings.backups_dir
    backup_database(keep=14)
    assert len(list_backups()) >= 2
    # create many and prune
    for _ in range(16):
        backup_database(keep=100)  # defer prune
    deleted = prune_backups(keep=14)
    assert len(list_backups()) == 14
    assert deleted >= 1


def test_auth_lock(client, monkeypatch, data_dir):
    monkeypatch.setattr(settings, "app_passphrase", "secret-pass")
    # locked
    r = client.get("/api/v1/profiles")
    assert r.status_code == 401
    assert r.json().get("code") == "app_locked"

    status = client.get("/api/v1/auth/status")
    assert status.json()["locked"] is True
    assert status.json()["unlocked"] is False

    bad = client.post("/api/v1/auth/unlock", json={"passphrase": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/api/v1/auth/unlock", json={"passphrase": "secret-pass"})
    assert ok.status_code == 200

    r = client.get("/api/v1/profiles")
    assert r.status_code == 200

    client.post("/api/v1/auth/lock")
    r = client.get("/api/v1/profiles")
    assert r.status_code == 401


def test_session_secret_generated_and_persisted(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "session_secret", None)
    monkeypatch.setattr(settings, "labledger_data_dir", tmp_path)
    k1 = settings.signing_key()
    assert len(k1) == 64 and "change-me" not in k1
    assert settings.signing_key() == k1  # persisted, stable across calls/restarts
    assert (tmp_path / ".session_secret").read_text() == k1
    monkeypatch.setattr(settings, "session_secret", "from-env")
    assert settings.signing_key() == "from-env"  # env wins


def test_cookie_secure_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "app_passphrase", "secret-pass")
    body = {"passphrase": "secret-pass"}
    plain = client.post("/api/v1/auth/unlock", json=body)
    assert "secure" not in plain.headers["set-cookie"].lower()
    proxied = client.post("/api/v1/auth/unlock", json=body, headers={"x-forwarded-proto": "https"})
    assert "secure" in proxied.headers["set-cookie"].lower()
    monkeypatch.setattr(settings, "cookie_secure", True)
    forced = client.post("/api/v1/auth/unlock", json=body)
    assert "secure" in forced.headers["set-cookie"].lower()


def test_biomarker_alt_unit_from_unit_conversion(client, data_dir):
    """After seeding a conversion row, list/detail expose alt_unit + alt_factor."""
    from app.db import session as db_session
    from app.models import Biomarker, UnitConversion

    db = db_session.SessionLocal()
    try:
        b = Biomarker(
            canonical_key="glucose_fasting",
            display_name="Glucose, Fasting",
            category="diabetes",
            canonical_unit="mg/dL",
            decimals=0,
            aliases=["FBS"],
        )
        db.add(b)
        db.flush()
        db.add(
            UnitConversion(
                biomarker_id=b.id,
                from_unit="mg/dL",
                to_unit="mmol/L",
                factor=0.0555,
                offset=0.0,
                source_note="test",
            )
        )
        # HbA1c-like non-affine should not become a simple toggle
        b2 = Biomarker(
            canonical_key="hba1c",
            display_name="HbA1c",
            category="diabetes",
            canonical_unit="%",
            decimals=1,
            aliases=[],
        )
        db.add(b2)
        db.flush()
        db.add(
            UnitConversion(
                biomarker_id=b2.id,
                from_unit="%",
                to_unit="mmol/mol",
                factor=10.929,
                offset=-2.15,
                source_note="formula",
            )
        )
        db.commit()
        gid, hid = b.id, b2.id
    finally:
        db.close()

    one = client.get(f"/api/v1/biomarkers/{gid}")
    assert one.status_code == 200
    body = one.json()
    assert body["alt_unit"] == "mmol/L"
    assert abs(body["alt_factor"] - 0.0555) < 1e-9

    lst = client.get("/api/v1/biomarkers", params={"q": "glucose"})
    assert lst.status_code == 200
    item = next(x for x in lst.json()["items"] if x["id"] == gid)
    assert item["alt_unit"] == "mmol/L"
    assert item["alt_factor"] == body["alt_factor"]

    h = client.get(f"/api/v1/biomarkers/{hid}").json()
    assert h["alt_unit"] is None
    assert h["alt_factor"] is None
