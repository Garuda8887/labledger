"""Nightly SQLite backup helper — keep last N under /data/backups."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.logging_utils import log_event

def _resolve_db_file() -> Path:
    """Resolve the live SQLite file (honours DATABASE_URL override)."""
    url = settings.sqlalchemy_url
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///"))
    return settings.db_path



def backup_database(*, keep: int | None = None) -> Path:
    """
    Copy the SQLite DB to /data/backups/labledger-YYYYMMDD-HHMMSS.db.
    Prune older backups beyond `keep` (default settings.backup_keep = 14).
    Returns the path of the new backup.
    """
    keep_n = keep if keep is not None else settings.backup_keep
    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    src = _resolve_db_file()
    if not src.exists():
        raise FileNotFoundError(f"Database not found at {src}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    dest = settings.backups_dir / f"labledger-{stamp}.db"
    # Prefer SQLite backup API when available; shutil is fine for WAL + checkpoint
    shutil.copy2(src, dest)
    # Also copy WAL/SHM if present for consistency
    for suffix in ("-wal", "-shm"):
        side = Path(str(src) + suffix)
        if side.exists():
            shutil.copy2(side, Path(str(dest) + suffix))

    log_event("backup_created", path=str(dest.name))
    prune_backups(keep=keep_n)
    return dest


def prune_backups(*, keep: int = 14) -> int:
    """Delete oldest backup files beyond keep. Returns number deleted."""
    backups = sorted(
        settings.backups_dir.glob("labledger-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for old in backups[keep:]:
        old.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm"):
            Path(str(old) + suffix).unlink(missing_ok=True)
        deleted += 1
        log_event("backup_pruned", path=old.name)
    return deleted


def list_backups() -> list[Path]:
    return sorted(
        settings.backups_dir.glob("labledger-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
