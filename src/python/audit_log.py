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

    def events_for_target(
        self,
        target_id: int,
        *,
        since_ms: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Return timeline-formatted events for the ActivityTimeline panel.

        Each event is `{timestamp, kind, label, detail, source}` matching the
        frontend `TimelineEvent` shape. Maps audit `action_type` strings into
        UI kinds (DETECTION / STATE / COA / ENGAGEMENT / BDA / OPERATOR / NOTE).
        """
        kind_map = {
            "target_state_transition": "STATE",
            "target_detected": "DETECTION",
            "target_classified": "STATE",
            "target_verified": "STATE",
            "nomination_approved": "OPERATOR",
            "nomination_rejected": "OPERATOR",
            "nomination_retasked": "OPERATOR",
            "coa_authorized": "COA",
            "coa_rejected": "COA",
            "engagement_executed": "ENGAGEMENT",
            "effector_dispatched": "ENGAGEMENT",
            "bda_completed": "BDA",
            "verify_target": "OPERATOR",
            "retask_sensors": "OPERATOR",
        }
        out: list[dict] = []
        with self._lock:
            for record in self._records:
                if record.target_id != target_id:
                    continue
                ts_ms = _isoformat_to_ms(record.timestamp)
                if since_ms is not None and ts_ms < since_ms:
                    continue
                kind = kind_map.get(record.action_type, "NOTE")
                details = record.details or {}
                # Build a human-readable label/detail
                label, detail = _format_event(record.action_type, details)
                out.append({
                    "timestamp": ts_ms,
                    "kind": kind,
                    "label": label,
                    "detail": detail,
                    "source": record.action_type,
                })
        return out[-limit:]


def _isoformat_to_ms(iso: str) -> int:
    """Best-effort ISO-8601 → epoch milliseconds."""
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:  # noqa: BLE001
        return 0


def _format_event(action: str, details: dict) -> tuple[str, str]:
    if action == "target_state_transition":
        return (
            f"State {details.get('from_state', '?')} → {details.get('to_state', '?')}",
            f"fused_confidence {details.get('fused_confidence', '?'):.2f}"
            if isinstance(details.get("fused_confidence"), (int, float))
            else "",
        )
    if action == "engagement_executed":
        eff = details.get("effector", "?")
        dmg = details.get("damage_level", "?")
        return (f"Engagement via {eff}: {dmg}", details.get("reasoning_trace", ""))
    if action == "effector_dispatched":
        return (
            f"{details.get('channel', '?')} mission {details.get('mission_id', '?')}",
            f"latency {details.get('latency_ms', '?')}ms · {details.get('detail', '')}".strip(),
        )
    if action == "nomination_approved":
        return ("Nomination approved", details.get("rationale", ""))
    if action == "nomination_rejected":
        return ("Nomination rejected", details.get("rationale", ""))
    if action == "nomination_retasked":
        return ("Nomination retasked", details.get("rationale", ""))
    if action == "coa_authorized":
        return ("COA authorized", details.get("coa_id", ""))
    if action == "verify_target":
        return ("Operator verify", details.get("rationale", ""))
    return (action, json.dumps(details, default=str))


# Module-level singleton for cross-module access
audit_log = AuditLog()
