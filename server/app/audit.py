from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog, utcnow


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def append_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any] | None = None,
    tenant_id: str = "demo-tenant",
    site_id: str | None = None,
    actor_type: str = "system",
    actor_id: str = "system",
    trace_id: str | None = None,
    occurred_at: datetime | None = None,
) -> AuditLog:
    previous = db.scalar(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    previous_hash = previous.entry_hash if previous else "GENESIS"
    timestamp = occurred_at or utcnow()
    trace = trace_id or f"trace-{uuid4().hex[:16]}"
    canonical = json.dumps(
        {
            "tenantId": tenant_id,
            "siteId": site_id,
            "occurredAt": timestamp.isoformat(),
            "actorType": actor_type,
            "actorId": actor_id,
            "action": action,
            "resourceType": resource_type,
            "resourceId": resource_id,
            "traceId": trace,
            "detail": detail or {},
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    entry_hash = hashlib.sha256(f"{previous_hash}:{canonical}".encode("utf-8")).hexdigest()
    log = AuditLog(
        tenant_id=tenant_id,
        site_id=site_id,
        occurred_at=timestamp,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        trace_id=trace,
        detail=detail or {},
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )
    db.add(log)
    db.flush()
    return log


def verify_audit_chain(db: Session, tenant_id: str = "demo-tenant") -> dict[str, Any]:
    entries = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.id.asc())
        )
    )
    expected_previous = "GENESIS"
    for entry in entries:
        if entry.previous_hash != expected_previous:
            return {"valid": False, "checked": len(entries), "brokenAtId": entry.id}
        expected_previous = entry.entry_hash
    return {
        "valid": True,
        "checked": len(entries),
        "headHash": entries[-1].entry_hash if entries else "GENESIS",
    }
