"""Audit log helpers (review edits). Values stored in DB only — not application logs."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    actor: str = "user",
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        actor=actor,
    )
    db.add(entry)
    return entry
