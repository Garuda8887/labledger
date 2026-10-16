#!/usr/bin/env python3
"""CLI: load catalog seed into SQLite. Invoked by `make seed-catalog`."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure api/ on path when run as script
API_ROOT = Path(__file__).resolve().parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.catalog.seed_loader import seed_catalog  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        counts = seed_catalog(db)
    finally:
        db.close()
    print("Catalog seed loaded:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
