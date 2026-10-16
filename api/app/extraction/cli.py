"""Thin CLI: extract-one <path> [--profile-id ...] [--persist]

Used by `make extract-one FILE=...` when A's job worker is not yet available.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Labledger extraction pipeline")
    parser.add_argument("path", type=Path, help="PDF or image to extract")
    parser.add_argument("--persist", action="store_true", help="Create profile/document and persist rows")
    parser.add_argument("--profile-id", default=None, help="Existing profile id when --persist")
    parser.add_argument("--profile-name", default="Extract CLI", help="Profile name if creating")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"File not found: {args.path}", file=sys.stderr)
        return 2

    from app.extraction.pipeline import process_document, process_file

    if not args.persist:
        result = process_file(args.path)
        summary = {
            "status": result.status,
            "source_type": result.source_type,
            "page_count": result.page_count,
            "meta": result.meta,
            "rows_extracted": result.rows_extracted,
            "error": result.error,
            "rows": [
                {
                    "raw_test_name": c.raw_test_name,
                    "raw_value": c.raw_value,
                    "raw_unit": c.raw_unit,
                    "raw_ref_text": c.raw_ref_text,
                    "comparator": c.comparator,
                    "value_numeric": c.value_numeric,
                    "flag": c.flag,
                    "confidence": c.confidence,
                    "confidence_reasons": c.confidence_reasons,
                    "page": c.page,
                }
                for c in result.candidates
            ],
        }
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"status={result.status} pages={result.page_count} rows={result.rows_extracted}")
            for c in result.candidates:
                print(
                    f"  - {c.raw_test_name}: {c.raw_value} {c.raw_unit or ''} "
                    f"[{c.flag}] conf={c.confidence:.2f}"
                )
            if result.error:
                print(f"error: {result.error}", file=sys.stderr)
                return 1
        return 0 if result.status != "failed" else 1

    # Persist path: ensure profile + document rows exist
    from app.db.session import SessionLocal, init_db
    from app.extraction.ingest import store_path
    from app.models.entities import Document, Profile

    init_db()
    db = SessionLocal()
    try:
        if args.profile_id:
            profile = db.get(Profile, args.profile_id)
            if profile is None:
                print(f"Profile not found: {args.profile_id}", file=sys.stderr)
                return 2
        else:
            profile = Profile(display_name=args.profile_name)
            db.add(profile)
            db.commit()
            db.refresh(profile)

        ingested = store_path(profile.id, args.path)
        doc = Document(
            profile_id=profile.id,
            original_filename=ingested.original_filename,
            sha256=ingested.sha256,
            mime=ingested.mime,
            stored_path=ingested.stored_path,
            source_type="digital_pdf" if ingested.mime == "application/pdf" else "image",
            status="processing",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        result = process_document(doc.id, session=db)
        summary = {
            "document_id": result.document_id,
            "profile_id": profile.id,
            "status": result.status,
            "rows_persisted": result.rows_persisted,
            "meta": result.meta,
            "error": result.error,
        }
        print(json.dumps(summary, indent=2) if args.json else summary)
        return 0 if result.status == "needs_review" else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
