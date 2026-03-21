"""After-Action Review Engine (W4-008).

Variable-speed replay from persisted snapshots, decision timeline by F2T2EA phase,
AI vs. operator comparison.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from audit_log import AuditLog
from mission_store import MissionStore

# F2T2EA phase mapping: event_type -> kill chain phase
_EVENT_TO_PHASE: dict[str, str] = {
    "DETECTED": "FIND",
    "CLASSIFIED": "FIX",
    "VERIFIED": "TRACK",
    "TRACKING": "TRACK",
    "NOMINATED": "TARGET",
    "COA_GENERATED": "TARGET",
    "AUTHORIZED": "ENGAGE",
    "ENGAGED": "ENGAGE",
    "BDA_COMPLETE": "ASSESS",
    "DESTROYED": "ASSESS",
    "MISS": "ASSESS",
}

_OPERATOR_OVERRIDE_ACTIONS = frozenset(
    {
        "REJECT_NOMINATION",
        "REJECT_COA",
        "OVERRIDE",
    }
)

_DECISION_ACTIONS = frozenset(
    {
        "APPROVE_NOMINATION",
        "REJECT_NOMINATION",
        "AUTHORIZE_COA",
        "REJECT_COA",
    }
)

_EMPTY_PHASES: dict[str, list[dict]] = {
    "FIND": [],
    "FIX": [],
    "TRACK": [],
    "TARGET": [],
    "ENGAGE": [],
    "ASSESS": [],
}


@dataclass(frozen=True)
class AARSnapshot:
    timestamp: str
    tick: int
    state_json: str
    decisions: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class AARTimeline:
    mission_id: int
    phases: dict[str, list[dict]]
    total_ticks: int
    duration_seconds: float


@dataclass(frozen=True)
class AARReport:
    mission_id: int
    theater: str
    duration_seconds: float
    targets_detected: int
    targets_engaged: int
    engagements_successful: int
    operator_overrides: int
    ai_acceptance_rate: float
    phase_breakdown: dict[str, dict]


def _parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _duration_between(start: str | None, end: str | None) -> float:
    if not start:
        return 0.0
    t_start = _parse_iso(start)
    t_end = _parse_iso(end) if end else datetime.now(timezone.utc)
    return max((t_end - t_start).total_seconds(), 0.0)


class AAREngine:
    def __init__(self, mission_store: MissionStore, audit_log: AuditLog) -> None:
        self._store = mission_store
        self._audit = audit_log

    def build_timeline(self, mission_id: int) -> AARTimeline:
        mission = self._store.get_mission(mission_id)
        events = self._get_all_target_events(mission_id)

        phases: dict[str, list[dict]] = {k: list(v) for k, v in _EMPTY_PHASES.items()}

        for event in events:
            phase = _EVENT_TO_PHASE.get(event["event_type"])
            if phase:
                phases[phase].append(event)

        duration = 0.0
        if mission:
            duration = _duration_between(mission.get("start_time"), mission.get("end_time"))

        total_ticks = len(events)

        return AARTimeline(
            mission_id=mission_id,
            phases=phases,
            total_ticks=total_ticks,
            duration_seconds=duration,
        )

    def get_snapshots(
        self,
        mission_id: int,
        start_tick: int = 0,
        end_tick: int | None = None,
        step: int = 1,
    ) -> list[AARSnapshot]:
        checkpoint_json = self._store.load_checkpoint(mission_id)
        if not checkpoint_json:
            return []

        state = json.loads(checkpoint_json)
        tick = state.get("tick", 0)
        now = datetime.now(timezone.utc).isoformat()

        audit_records = self._audit.query(target_id=None)
        decisions = [r for r in audit_records if r.get("action_type") in _DECISION_ACTIONS]

        snapshot = AARSnapshot(
            timestamp=now,
            tick=tick,
            state_json=checkpoint_json,
            decisions=decisions,
        )
        return [snapshot]

    def compare_decisions(self, mission_id: int) -> list[dict]:
        records = self._audit.to_json()
        if not records:
            return []

        comparisons = []
        for record in records:
            action = record.get("action_type", "")
            if action not in _DECISION_ACTIONS:
                continue
            autonomy = record.get("autonomy_level", "")
            operator_id = record.get("operator_id")

            is_operator = operator_id is not None and autonomy in ("MANUAL", "SUPERVISED")
            is_ai = autonomy == "AUTONOMOUS"

            comparisons.append(
                {
                    "action": action,
                    "target_id": record.get("target_id"),
                    "autonomy_level": autonomy,
                    "operator_id": operator_id,
                    "is_operator_decision": is_operator,
                    "is_ai_decision": is_ai,
                    "timestamp": record.get("timestamp"),
                }
            )

        return comparisons

    def generate_report(self, mission_id: int) -> AARReport:
        mission = self._store.get_mission(mission_id)
        if not mission:
            return self._empty_report(mission_id)

        summary = self._store.get_mission_summary(mission_id)
        timeline = self.build_timeline(mission_id)
        audit_records = self._audit.to_json()

        duration = _duration_between(mission.get("start_time"), mission.get("end_time"))
        targets_detected = self._count_unique_targets_by_event(mission_id, "DETECTED")
        outcomes = summary.get("outcomes", {})
        engagements_successful = outcomes.get("HIT", 0)
        targets_engaged = summary.get("engagements", 0)

        overrides = sum(1 for r in audit_records if r.get("action_type") in _OPERATOR_OVERRIDE_ACTIONS)

        total_decisions = sum(1 for r in audit_records if r.get("action_type") in _DECISION_ACTIONS)
        ai_decisions = sum(
            1
            for r in audit_records
            if r.get("action_type") in _DECISION_ACTIONS and r.get("autonomy_level") == "AUTONOMOUS"
        )
        ai_rate = (ai_decisions / total_decisions) if total_decisions > 0 else 0.0

        phase_breakdown = {}
        for phase, events in timeline.phases.items():
            phase_breakdown[phase] = {"event_count": len(events)}

        return AARReport(
            mission_id=mission_id,
            theater=mission.get("theater", "unknown"),
            duration_seconds=duration,
            targets_detected=targets_detected,
            targets_engaged=targets_engaged,
            engagements_successful=engagements_successful,
            operator_overrides=overrides,
            ai_acceptance_rate=ai_rate,
            phase_breakdown=phase_breakdown,
        )

    def _empty_report(self, mission_id: int) -> AARReport:
        return AARReport(
            mission_id=mission_id,
            theater="unknown",
            duration_seconds=0.0,
            targets_detected=0,
            targets_engaged=0,
            engagements_successful=0,
            operator_overrides=0,
            ai_acceptance_rate=0.0,
            phase_breakdown={p: {"event_count": 0} for p in _EMPTY_PHASES},
        )

    def _get_all_target_events(self, mission_id: int) -> list[dict]:
        with self._store._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM target_events WHERE mission_id = ? ORDER BY timestamp ASC",
                (mission_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def _count_unique_targets_by_event(self, mission_id: int, event_type: str) -> int:
        with self._store._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT target_id) FROM target_events WHERE mission_id = ? AND event_type = ?",
                (mission_id, event_type),
            ).fetchone()
            return row[0] if row else 0
