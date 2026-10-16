"""Ingestion and extraction pipeline.

Entrypoint for A's job worker:
    from app.extraction import process_document
    process_document(document_id)

Standalone (no worker yet):
    python -m app.extraction.cli path/to/file.pdf
    make extract-one FILE=path/to/file.pdf
"""
from app.extraction.pipeline import process_document, process_file, PipelineResult
from app.extraction.ingest import store_bytes, store_path, IngestResult, IngestError

__all__ = [
    "process_document",
    "process_file",
    "PipelineResult",
    "store_bytes",
    "store_path",
    "IngestResult",
    "IngestError",
]
