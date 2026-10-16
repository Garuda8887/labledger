import shutil

import pytest

from app.services.jobs import run_pending_jobs_once


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")

def test_upload_image_and_status(client, two_profiles, sample_png_bytes):
    a, _ = two_profiles
    files = {"files": ("report.png", sample_png_bytes, "image/png")}
    r = client.post(f"/api/v1/profiles/{a['id']}/documents", files=files)
    assert r.status_code == 202, r.text
    body = r.json()
    assert len(body["documents"]) == 1
    assert len(body["jobs"]) == 1
    doc = body["documents"][0]
    assert doc["status"] == "processing"
    assert doc["profile_id"] == a["id"]
    job_id = body["jobs"][0]["id"]

    # Process job synchronously (worker may be stopped in fixture)
    run_pending_jobs_once()

    st = client.get(f"/api/v1/documents/{doc['id']}/status")
    assert st.status_code == 200
    assert st.json()["status"] == "needs_review"

    job = client.get(f"/api/v1/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"

    page = client.get(f"/api/v1/documents/{doc['id']}/pages/1")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("image/")


def test_upload_duplicate_warns(client, two_profiles, sample_png_bytes):
    a, _ = two_profiles
    files = {"files": ("report.png", sample_png_bytes, "image/png")}
    r1 = client.post(f"/api/v1/profiles/{a['id']}/documents", files=files)
    assert r1.status_code == 202
    r2 = client.post(f"/api/v1/profiles/{a['id']}/documents", files=files)
    assert r2.status_code == 202
    assert r2.json()["documents"] == []
    assert len(r2.json()["duplicates"]) == 1
    assert r2.json()["duplicates"][0]["code"] == "duplicate"


def test_multi_page_merge(client, two_profiles, sample_png_bytes):
    a, _ = two_profiles
    files = [
        ("files", ("p1.png", sample_png_bytes, "image/png")),
        ("files", ("p2.png", sample_png_bytes, "image/png")),
    ]
    r = client.post(
        f"/api/v1/profiles/{a['id']}/documents",
        files=files,
        data={"multi_page": "true"},
    )
    assert r.status_code == 202, r.text
    doc = r.json()["documents"][0]
    assert doc["source_type"] == "multi_image"
    assert doc["page_count"] == 2


def test_document_list_isolated(client, two_profiles, sample_png_bytes):
    a, b = two_profiles
    client.post(
        f"/api/v1/profiles/{a['id']}/documents",
        files={"files": ("a.png", sample_png_bytes, "image/png")},
    )
    client.post(
        f"/api/v1/profiles/{b['id']}/documents",
        files={"files": ("b.png", sample_png_bytes, "image/png")},
    )
    la = client.get(f"/api/v1/profiles/{a['id']}/documents").json()
    lb = client.get(f"/api/v1/profiles/{b['id']}/documents").json()
    assert la["total"] == 1
    assert lb["total"] == 1
    assert la["items"][0]["profile_id"] == a["id"]
    assert lb["items"][0]["profile_id"] == b["id"]
