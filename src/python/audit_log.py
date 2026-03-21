"""Structured audit trail with SHA-256 hash chain for tamper evidence (W3-002)."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class AuditRecord:
    timestamp: str
    action_type: str
    autonomy_level: str
    target_id: int | None
    drone_id: int | None
    operator_id: str | None
    sensor_evidence: dict | None
    hitl_status: str | None
    details: dict
    prev_hash: str
    record_hash: str


def _compute_hash(content: dict, prev_hash: str) -> str:
    payload = json.dumps(content, sort_keys=True, default=str) + prev_hash
    return hashlib.sha256(payload.encode()).hexdigest()


def _record_content(record: AuditRecord) -> dict:
    d = asdict(record)
    d.pop("record_hash")
    d.pop("prev_hash")
    return d


class AuditLog:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._lock = threading.Lock()

    def append(
        self,
        action_type: str,
        *,
        autonomy_level: str = "MANUAL",
        target_id: int | None = None,
        drone_id: int | None = None,
        operator_id: str | None = None,
        sensor_evidence: dict | None = None,
        hitl_status: str | None = None,
        details: dict | None = None,
    ) -> AuditRecord:
        with self._lock:
            prev_hash = self._records[-1].record_hash if self._records else "0" * 64
            content = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_type": action_type,
                "autonomy_level": autonomy_level,
                "target_id": target_id,
                "drone_id": drone_id,
                "operator_id": operator_id,
                "sensor_evidence": sensor_evidence,
                "hitl_status": hitl_status,
                "details": details or {},
            }
            record_hash = _compute_hash(content, prev_hash)
            record = AuditRecord(
                **content,
                prev_hash=prev_hash,
                record_hash=record_hash,
            )
            self._records = [*self._records, record]
            return record

    def verify_chain(self) -> bool:
        prev_hash = "0" * 64
        for record in self._records:
            if record.prev_hash != prev_hash:
                return False
            content = _record_content(record)
            expected_hash = _compute_hash(content, prev_hash)
            if record.record_hash != expected_hash:
                return False
            prev_hash = record.record_hash
        return True

    def query(
        self,
        *,
        action_type: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        autonomy_level: str | None = None,
        target_id: int | None = None,
    ) -> list[dict]:
        results = []
        for record in self._records:
            if action_type and record.action_type != action_type:
                continue
            if autonomy_level and record.autonomy_level != autonomy_level:
                continue
            if target_id is not None and record.target_id != target_id:
                continue
            if start_time and record.timestamp < start_time:
                continue
            if end_time and record.timestamp > end_time:
                continue
            results.append(asdict(record))
        return results

    def to_json(self) -> list[dict]:
        return [asdict(r) for r in self._records]


# Module-level singleton for cross-module access
audit_log = AuditLog()
