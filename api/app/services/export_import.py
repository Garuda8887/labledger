"""Per-profile export/import as zip (JSON rows + original files)."""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_utils import log_event
from app.models import Document, LearnedAlias, Profile, Result
from app.services import storage


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def _row_to_dict(obj: Any, fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields:
        out[f] = getattr(obj, f)
    return out


PROFILE_FIELDS = [
    "id",
    "display_name",
    "dob",
    "sex",
    "preferred_unit_system",
    "created_at",
]
DOCUMENT_FIELDS = [
    "id",
    "profile_id",
    "original_filename",
    "sha256",
    "mime",
    "stored_path",
    "source_type",
    "page_count",
    "lab_name",
    "report_date",
    "collected_at",
    "sample_id",
    "printed_patient_name",
    "printed_patient_age",
    "printed_patient_sex",
    "status",
    "uploaded_at",
]
RESULT_FIELDS = [
    "id",
    "document_id",
    "profile_id",
    "page",
    "bbox",
    "raw_test_name",
    "raw_value",
    "raw_unit",
    "raw_ref_text",
    "biomarker_id",
    "comparator",
    "value_numeric",
    "value_qualitative",
    "normalized_value",
    "canonical_unit",
    "ref_low",
    "ref_high",
    "ref_source",
    "flag",
    "collected_at",
    "confidence",
    "confidence_reasons",
    "status",
    "reviewed_at",
]


def export_profile_zip(db: Session, profile_id: str) -> Path:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise LookupError("profile not found")

    docs = db.query(Document).filter(Document.profile_id == profile_id).all()
    results = db.query(Result).filter(Result.profile_id == profile_id).all()

    tmp = Path(tempfile.mkdtemp(prefix="labledger-export-"))
    try:
        meta = {
            "format": "labledger-profile-export",
            "version": 1,
            "profile": _row_to_dict(profile, PROFILE_FIELDS),
            "documents": [_row_to_dict(d, DOCUMENT_FIELDS) for d in docs],
            "results": [_row_to_dict(r, RESULT_FIELDS) for r in results],
        }
        (tmp / "profile.json").write_text(
            json.dumps(meta, default=_json_default, indent=2),
            encoding="utf-8",
        )

        files_root = tmp / "files"
        files_root.mkdir()
        for doc in docs:
            src = storage.resolve_stored_path(doc.stored_path)
            if src.exists():
                # Preserve relative structure under files/
                rel = Path(doc.stored_path)
                if rel.is_absolute():
                    dest = files_root / doc.sha256 / src.name
                else:
                    # stored_path like files/<profile>/<sha>/original/name
                    parts = rel.parts
                    if parts and parts[0] == "files":
                        dest = files_root / Path(*parts[1:])
                    else:
                        dest = files_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if src.is_file():
                    shutil.copy2(src, dest)
                # Copy sibling pages dir if present
                pages = src.parent.parent / "pages" if src.parent.name == "original" else src.parent / "pages"
                if pages.is_dir():
                    dest_pages = dest.parent.parent / "pages"
                    if not dest_pages.exists():
                        shutil.copytree(pages, dest_pages)

        out_dir = settings.labledger_data_dir / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"profile-{profile_id}.zip"
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in tmp.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(tmp).as_posix())

        log_event("profile_exported", profile_id=profile_id)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def import_profile_zip(
    db: Session,
    zip_path: Path,
    *,
    as_new: bool = True,
) -> Profile:
    """
    Import a profile export zip.
    as_new=True always creates a new profile id (safe default for isolation).
    """
    import uuid

    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("profile.json") as f:
            meta = json.load(f)

    if meta.get("format") != "labledger-profile-export":
        raise ValueError("Not a Labledger profile export")

    pdata = meta["profile"]
    new_id = str(uuid.uuid4()) if as_new else pdata["id"]
    id_map_docs: dict[str, str] = {}

    profile = Profile(
        id=new_id,
        display_name=pdata["display_name"],
        dob=date.fromisoformat(pdata["dob"]) if pdata.get("dob") else None,
        sex=pdata.get("sex") or "unspecified",
        preferred_unit_system=pdata.get("preferred_unit_system") or "conventional",
    )
    db.add(profile)
    db.flush()

    # Extract files into new profile dir
    with zipfile.ZipFile(zip_path, "r") as zf:
        for doc_data in meta.get("documents", []):
            old_doc_id = doc_data["id"]
            new_doc_id = str(uuid.uuid4()) if as_new else old_doc_id
            id_map_docs[old_doc_id] = new_doc_id
            sha = doc_data["sha256"]

            # Find original in zip
            candidates = [
                n
                for n in zf.namelist()
                if n.startswith("files/") and sha in n and "/original/" in n
            ]
            stored_rel = doc_data["stored_path"]
            if candidates:
                member = candidates[0]
                data = zf.read(member)
                fname = Path(member).name
                rel = storage.store_original(new_id, sha, fname, data)
                stored_rel = str(rel)
                # pages
                for n in zf.namelist():
                    if n.startswith(f"files/") and sha in n and "/pages/" in n:
                        page_name = Path(n).name
                        page_data = zf.read(n)
                        page_dest = storage.pages_dir(new_id, sha) / page_name
                        page_dest.write_bytes(page_data)

            doc = Document(
                id=new_doc_id,
                profile_id=new_id,
                original_filename=doc_data["original_filename"],
                sha256=sha,
                mime=doc_data["mime"],
                stored_path=stored_rel,
                source_type=doc_data["source_type"],
                page_count=doc_data.get("page_count") or 1,
                lab_name=doc_data.get("lab_name"),
                report_date=(
                    date.fromisoformat(doc_data["report_date"])
                    if doc_data.get("report_date")
                    else None
                ),
                collected_at=(
                    datetime.fromisoformat(doc_data["collected_at"])
                    if doc_data.get("collected_at")
                    else None
                ),
                sample_id=doc_data.get("sample_id"),
                printed_patient_name=doc_data.get("printed_patient_name"),
                printed_patient_age=doc_data.get("printed_patient_age"),
                printed_patient_sex=doc_data.get("printed_patient_sex"),
                status=doc_data.get("status") or "confirmed",
            )
            db.add(doc)

        for rdata in meta.get("results", []):
            old_doc = rdata["document_id"]
            new_doc = id_map_docs.get(old_doc, old_doc)
            result = Result(
                id=str(uuid.uuid4()) if as_new else rdata["id"],
                document_id=new_doc,
                profile_id=new_id,
                page=rdata.get("page") or 1,
                bbox=rdata.get("bbox"),
                raw_test_name=rdata["raw_test_name"],
                raw_value=rdata["raw_value"],
                raw_unit=rdata.get("raw_unit"),
                raw_ref_text=rdata.get("raw_ref_text"),
                biomarker_id=rdata.get("biomarker_id"),
                comparator=rdata.get("comparator") or "=",
                value_numeric=rdata.get("value_numeric"),
                value_qualitative=rdata.get("value_qualitative"),
                normalized_value=rdata.get("normalized_value"),
                canonical_unit=rdata.get("canonical_unit"),
                ref_low=rdata.get("ref_low"),
                ref_high=rdata.get("ref_high"),
                ref_source=rdata.get("ref_source"),
                flag=rdata.get("flag") or "unknown",
                collected_at=(
                    datetime.fromisoformat(rdata["collected_at"])
                    if rdata.get("collected_at")
                    else None
                ),
                confidence=rdata.get("confidence") or 0.0,
                confidence_reasons=rdata.get("confidence_reasons") or [],
                status=rdata.get("status") or "pending_review",
                reviewed_at=(
                    datetime.fromisoformat(rdata["reviewed_at"])
                    if rdata.get("reviewed_at")
                    else None
                ),
            )
            db.add(result)

    db.commit()
    db.refresh(profile)
    log_event("profile_imported", profile_id=profile.id)
    return profile
