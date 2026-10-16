from app.db.session import SessionLocal
from app.models import Result
from app.services.jobs import run_pending_jobs_once


def _upload_and_add_result(client, profile, png, biomarker_id=None):
    r = client.post(
        f"/api/v1/profiles/{profile['id']}/documents",
        files={"files": ("lab.png", png, "image/png")},
    )
    assert r.status_code == 202
    doc = r.json()["documents"][0]
    run_pending_jobs_once()
    body = {
        "document_id": doc["id"],
        "profile_id": profile["id"],
        "raw_test_name": "Hb",
        "raw_value": "13.2",
        "raw_unit": "g/dL",
        "value_numeric": 13.2,
        "normalized_value": 13.2,
        "canonical_unit": "g/dL",
        "flag": "normal",
        "biomarker_id": biomarker_id,
    }
    add = client.post("/api/v1/results", json=body)
    assert add.status_code == 201, add.text
    return doc, add.json()


def test_review_confirm_edit_reject(client, two_profiles, sample_png_bytes, seed_biomarker):
    a, _ = two_profiles
    doc, result = _upload_and_add_result(client, a, sample_png_bytes, seed_biomarker["id"])
    rid = result["id"]

    edited = client.patch(
        f"/api/v1/results/{rid}",
        json={"raw_value": "13.5", "value_numeric": 13.5, "remember_mapping": True},
    )
    assert edited.status_code == 200
    assert edited.json()["raw_value"] == "13.5"

    aliases = client.get("/api/v1/learned-aliases")
    assert aliases.status_code == 200
    assert any(x["raw_name_normalized"] == "hb" for x in aliases.json())

    conf = client.post(f"/api/v1/results/{rid}/confirm")
    assert conf.status_code == 200
    assert conf.json()["status"] == "confirmed"

    # add another pending and reject
    _, r2 = _upload_and_add_result(client, a, sample_png_bytes + b"\x00", seed_biomarker["id"])
    # duplicate content may fail — force unique bytes
    rej = client.post(f"/api/v1/results/{r2['id']}/reject")
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"


def test_bulk_confirm_and_filters(client, two_profiles, sample_png_bytes, seed_biomarker):
    a, b = two_profiles
    doc, r1 = _upload_and_add_result(client, a, sample_png_bytes, seed_biomarker["id"])
    # second result same doc
    r2 = client.post(
        "/api/v1/results",
        json={
            "document_id": doc["id"],
            "profile_id": a["id"],
            "raw_test_name": "RBC",
            "raw_value": "4.5",
            "value_numeric": 4.5,
            "biomarker_id": seed_biomarker["id"],
        },
    ).json()

    # Isolation: profile B sees none
    empty = client.get("/api/v1/results", params={"profile_id": b["id"]})
    assert empty.json()["total"] == 0

    bulk = client.post(
        "/api/v1/results/bulk-confirm",
        json={"document_id": doc["id"], "min_confidence": 0.9},
    )
    assert bulk.status_code == 200
    assert bulk.json()["count"] == 2

    listed = client.get(
        "/api/v1/results",
        params={"profile_id": a["id"], "status": "confirmed", "biomarker_id": seed_biomarker["id"]},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    cat = client.get(
        "/api/v1/results",
        params={"profile_id": a["id"], "category": "cbc"},
    )
    assert cat.status_code == 200
    assert cat.json()["total"] >= 1


def test_learned_alias_endpoint(client, seed_biomarker):
    r = client.post(
        "/api/v1/learned-aliases",
        json={"raw_name": "  Haemoglobin  ", "biomarker_id": seed_biomarker["id"]},
    )
    assert r.status_code == 201
    assert r.json()["raw_name_normalized"] == "haemoglobin"
