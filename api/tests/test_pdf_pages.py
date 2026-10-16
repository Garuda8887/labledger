import fitz

from app.extraction.digital import render_pdf_pages_to_dir
from app.services.jobs import run_pending_jobs_once


def _tiny_pdf(pages: int = 2) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page(width=300, height=200)
        p.insert_text((20, 50), f"Hemoglobin 13.{i} g/dL 12.0-15.5", fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def test_render_helper(tmp_path):
    pdf = tmp_path / "t.pdf"
    pdf.write_bytes(_tiny_pdf(2))
    n = render_pdf_pages_to_dir(pdf, tmp_path / "pages", dpi=150)
    assert n == 2
    png = (tmp_path / "pages" / "1.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "pages" / "2.png").exists()


def test_pdf_upload_process_pages(client, two_profiles):
    a, _ = two_profiles
    files = {"files": ("r.pdf", _tiny_pdf(2), "application/pdf")}
    r = client.post(f"/api/v1/profiles/{a['id']}/documents", files=files)
    assert r.status_code == 202, r.text
    doc = r.json()["documents"][0]
    assert doc["page_count"] == 2
    # page 1 available early, before the job runs
    assert client.get(f"/api/v1/documents/{doc['id']}/pages/1").status_code == 200

    run_pending_jobs_once()
    st = client.get(f"/api/v1/documents/{doc['id']}/status").json()
    assert st["page_count"] == 2
    for n in (1, 2):
        pg = client.get(f"/api/v1/documents/{doc['id']}/pages/{n}")
        assert pg.status_code == 200
        assert pg.headers["content-type"] == "image/png"
    assert client.get(f"/api/v1/documents/{doc['id']}/pages/3").status_code == 404
