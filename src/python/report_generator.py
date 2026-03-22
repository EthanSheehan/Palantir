"""Export/Reporting Module (W5-008).

Stateless ReportGenerator class producing mission reports in JSON and CSV
formats: target lifecycle, engagement outcomes, AI decision audit trail.

All methods are pure functions — caller supplies data, no I/O or side effects.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

_SUPPORTED_FORMATS = frozenset({"json", "csv"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_format(fmt: str) -> None:
    if fmt not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{fmt}'. Use one of: {sorted(_SUPPORTED_FORMATS)}")


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


class ReportGenerator:
    """Stateless report generator — all methods return serialized strings."""

    # ------------------------------------------------------------------
    # Target lifecycle
    # ------------------------------------------------------------------

    def generate_target_report(self, targets: list[dict], fmt: str = "json") -> str:
        """Generate a target lifecycle report.

        Args:
            targets: list of target dicts (id, type, state, kill_chain_phase, etc.)
            fmt: "json" or "csv"

        Returns:
            Serialized report string.
        """
        _validate_format(fmt)
        records = [dict(t) for t in targets]

        if fmt == "json":
            return json.dumps(
                {
                    "report_type": "target_lifecycle",
                    "generated_at": _now_iso(),
                    "total_targets": len(records),
                    "records": records,
                },
                default=str,
            )

        return self._target_lifecycle_csv(records)

    def _target_lifecycle_csv(self, records: list[dict]) -> str:
        headers = [
            "id",
            "type",
            "state",
            "lat",
            "lon",
            "kill_chain_phase",
            "detected_at",
            "verified_at",
            "engaged_at",
            "destroyed_at",
        ]
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        for rec in records:
            writer.writerow([_to_str(rec.get(h)) for h in headers])
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Engagement outcomes
    # ------------------------------------------------------------------

    def generate_engagement_report(self, engagements: list[dict], fmt: str = "json") -> str:
        """Generate an engagement outcomes report.

        Args:
            engagements: list of engagement dicts (target_id, drone_id, outcome, etc.)
            fmt: "json" or "csv"

        Returns:
            Serialized report string.
        """
        _validate_format(fmt)
        records = [dict(e) for e in engagements]

        if fmt == "json":
            total = len(records)
            hits = sum(1 for r in records if r.get("outcome") == "HIT")
            misses = sum(1 for r in records if r.get("outcome") == "MISS")
            return json.dumps(
                {
                    "report_type": "engagement_outcomes",
                    "generated_at": _now_iso(),
                    "summary": {
                        "total": total,
                        "hits": hits,
                        "misses": misses,
                    },
                    "records": records,
                },
                default=str,
            )

        return self._engagement_csv(records)

    def _engagement_csv(self, records: list[dict]) -> str:
        headers = [
            "target_id",
            "drone_id",
            "timestamp",
            "outcome",
            "coa_id",
            "autonomy_level",
        ]
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        for rec in records:
            writer.writerow([_to_str(rec.get(h)) for h in headers])
        return buf.getvalue()

    # ------------------------------------------------------------------
    # AI decision audit trail
    # ------------------------------------------------------------------

    def generate_audit_report(self, audit_entries: list[dict], fmt: str = "json") -> str:
        """Generate an AI decision audit trail report.

        Args:
            audit_entries: list of audit record dicts (from AuditLog.to_json())
            fmt: "json" or "csv"

        Returns:
            Serialized report string.
        """
        _validate_format(fmt)
        records = [dict(e) for e in audit_entries]

        if fmt == "json":
            return json.dumps(
                {
                    "report_type": "ai_decision_audit",
                    "generated_at": _now_iso(),
                    "total_entries": len(records),
                    "records": records,
                },
                default=str,
            )

        return self._audit_csv(records)

    def _audit_csv(self, records: list[dict]) -> str:
        headers = [
            "timestamp",
            "action_type",
            "autonomy_level",
            "target_id",
            "drone_id",
            "operator_id",
            "hitl_status",
            "record_hash",
            "prev_hash",
        ]
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        for rec in records:
            writer.writerow([_to_str(rec.get(h)) for h in headers])
        return buf.getvalue()
