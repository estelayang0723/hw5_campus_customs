"""Append-only JSON-array audit trail for PydanticAI graph steps."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any

from backend.config import AUDIT_PATH
from backend.models import AuditRecord


def append_audit_record(record: AuditRecord, path: Path = AUDIT_PATH) -> None:
    """Append one record to a valid JSON array without replacing prior records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    with os.fdopen(descriptor, "r+b") as file:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)
        try:
            file.seek(0)
            raw = file.read()
            if not raw.strip():
                file.seek(0)
                file.write(b"[\n" + encoded + b"\n]\n")
                file.flush()
                os.fsync(file.fileno())
                return

            existing: Any = json.loads(raw)
            if not isinstance(existing, list):
                raise ValueError(f"Audit trail must be a JSON array: {path}")
            trimmed = raw.rstrip()
            if not trimmed.endswith(b"]"):
                raise ValueError(f"Audit trail JSON array is incomplete: {path}")
            separator = b"\n" if not existing else b",\n"
            file.seek(len(trimmed) - 1)
            file.truncate()
            file.write(separator + encoded + b"\n]\n")
            file.flush()
            os.fsync(file.fileno())
        finally:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
