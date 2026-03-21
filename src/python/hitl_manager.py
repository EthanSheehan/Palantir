"""
hitl_manager.py
===============
Human-in-the-Loop (HITL) gate system for the strike board.

Two approval gates:
  Gate 1 — Target nomination: operator approves/rejects/retasks a nominated target.
  Gate 2 — COA authorization: operator selects one COA for execution.

All entries are immutable frozen dataclasses. Status transitions produce new
instances; the original is never mutated.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Immutable domain objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrikeBoardEntry:
    id: str
    target_id: int
    target_type: str
    target_location: tuple[float, float]
    detection_confidence: float
    priority_score: float
    roe_evaluation: str
    reasoning_trace: str
    status: str  # PENDING, APPROVED, REJECTED, RETASKED
    nominated_at: str  # ISO timestamp
    decision: Optional[dict] = None  # {action, rationale, timestamp}
    explanation: Optional[dict] = None  # DecisionExplanation.to_dict()


@dataclass(frozen=True)
class CourseOfAction:
    id: str  # "COA-1", "COA-2", "COA-3"
    effector_name: str
    effector_type: str
    time_to_effect_min: float
    pk_estimate: float
    risk_score: float
    composite_score: float
    reasoning_trace: str
    status: str  # PROPOSED, AUTHORIZED, REJECTED, EXECUTING, COMPLETE


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_decision(action: str, rationale: str) -> dict:
    return {"action": action, "rationale": rationale, "timestamp": _now_iso()}


# ---------------------------------------------------------------------------
# HITL Manager
# ---------------------------------------------------------------------------


class HITLManager:
    """Manages the strike board and human approval gates."""

    def __init__(self) -> None:
        self._strike_board: list[StrikeBoardEntry] = []
        self._coa_proposals: dict[str, list[CourseOfAction]] = {}  # strike_id -> COAs

    # ── Gate 1: Target nomination ──────────────────────────────────────────

    def nominate_target(
        self,
        target_data: dict,
        evaluation: dict,
    ) -> StrikeBoardEntry:
        """Add a target to the strike board as PENDING (Gate 1)."""
        entry = StrikeBoardEntry(
            id=f"SB-{uuid.uuid4().hex[:8].upper()}",
            target_id=target_data.get("target_id", 0),
            target_type=target_data.get("target_type", "UNKNOWN"),
            target_location=tuple(target_data.get("target_location", (0.0, 0.0))),
            detection_confidence=target_data.get("detection_confidence", 0.0),
            priority_score=evaluation.get("priority_score", 0.0),
            roe_evaluation=evaluation.get("roe_evaluation", "UNKNOWN"),
            reasoning_trace=evaluation.get("reasoning_trace", ""),
            status="PENDING",
            nominated_at=_now_iso(),
        )
        self._strike_board = [*self._strike_board, entry]
        logger.info("target_nominated", entry_id=entry.id, target_type=entry.target_type)
        return entry

    def approve_nomination(self, entry_id: str, rationale: str = "") -> StrikeBoardEntry:
        """Operator approves a target for COA generation."""
        return self._transition_entry(entry_id, "APPROVED", rationale)

    def reject_nomination(self, entry_id: str, rationale: str = "") -> StrikeBoardEntry:
        """Operator rejects a target."""
        return self._transition_entry(entry_id, "REJECTED", rationale)

    def retask_nomination(self, entry_id: str, rationale: str = "") -> StrikeBoardEntry:
        """Operator requests more intel on this target."""
        return self._transition_entry(entry_id, "RETASKED", rationale)

    # ── Gate 2: COA authorization ──────────────────────────────────────────

    def propose_coas(self, entry_id: str, coas: list[CourseOfAction]) -> None:
        """Present COAs for operator authorization (Gate 2)."""
        self._coa_proposals = {**self._coa_proposals, entry_id: list(coas)}
        logger.info("coas_proposed", entry_id=entry_id, count=len(coas))

    def authorize_coa(
        self,
        entry_id: str,
        coa_id: str,
        rationale: str = "",
    ) -> CourseOfAction:
        """Operator authorizes a specific COA for execution."""
        coas = self._coa_proposals.get(entry_id, [])
        target_coa = next((c for c in coas if c.id == coa_id), None)
        if target_coa is None:
            raise ValueError(f"COA {coa_id} not found for entry {entry_id}")

        authorized = replace(target_coa, status="AUTHORIZED")
        updated_coas = [authorized if c.id == coa_id else c for c in coas]
        self._coa_proposals = {**self._coa_proposals, entry_id: updated_coas}
        logger.info("coa_authorized", entry_id=entry_id, coa_id=coa_id)
        return authorized

    def reject_coa(self, entry_id: str, rationale: str = "") -> None:
        """Operator rejects all COAs for a strike board entry."""
        coas = self._coa_proposals.get(entry_id, [])
        rejected_coas = [replace(c, status="REJECTED") for c in coas]
        self._coa_proposals = {**self._coa_proposals, entry_id: rejected_coas}
        logger.info("coas_rejected", entry_id=entry_id, rationale=rationale)

    # ── Queries ────────────────────────────────────────────────────────────

    def get_strike_board(self) -> list[dict]:
        """Return current strike board state for the frontend."""
        return [
            {
                "id": e.id,
                "target_id": e.target_id,
                "target_type": e.target_type,
                "target_location": list(e.target_location),
                "detection_confidence": e.detection_confidence,
                "priority_score": e.priority_score,
                "roe_evaluation": e.roe_evaluation,
                "reasoning_trace": e.reasoning_trace,
                "status": e.status,
                "nominated_at": e.nominated_at,
                "decision": e.decision,
                "explanation": e.explanation,
            }
            for e in self._strike_board
        ]

    def get_coas_for_entry(self, entry_id: str) -> list[dict]:
        """Return COA proposals for a strike board entry."""
        coas = self._coa_proposals.get(entry_id, [])
        return [
            {
                "id": c.id,
                "effector_name": c.effector_name,
                "effector_type": c.effector_type,
                "time_to_effect_min": c.time_to_effect_min,
                "pk_estimate": c.pk_estimate,
                "risk_score": c.risk_score,
                "composite_score": c.composite_score,
                "reasoning_trace": c.reasoning_trace,
                "status": c.status,
            }
            for c in coas
        ]

    # ── Internal ───────────────────────────────────────────────────────────

    def _transition_entry(
        self,
        entry_id: str,
        new_status: str,
        rationale: str,
    ) -> StrikeBoardEntry:
        """Create a new entry with updated status, replacing the old one."""
        idx, old = self._find_entry(entry_id)
        if old.status != "PENDING":
            logger.warning(
                "security_replay_attempt",
                entry_id=entry_id,
                current_status=old.status,
                attempted_status=new_status,
            )
            raise ValueError(
                f"Cannot transition entry {entry_id} from status {old.status!r}: only PENDING entries can be transitioned"
            )
        updated = replace(
            old,
            status=new_status,
            decision=_make_decision(new_status, rationale),
        )
        self._strike_board = [updated if i == idx else e for i, e in enumerate(self._strike_board)]
        try:
            from audit_log import audit_log

            audit_log.append(
                "HITL_TRANSITION",
                target_id=old.target_id,
                hitl_status=new_status,
                details={
                    "entry_id": entry_id,
                    "from_status": old.status,
                    "to_status": new_status,
                    "rationale": rationale,
                },
            )
        except Exception:
            pass
        logger.info(
            "strike_board_transition",
            entry_id=entry_id,
            old_status=old.status,
            new_status=new_status,
        )
        return updated

    def _find_entry(self, entry_id: str) -> tuple[int, StrikeBoardEntry]:
        """Locate an entry by ID. Raises ValueError if not found."""
        for i, entry in enumerate(self._strike_board):
            if entry.id == entry_id:
                return i, entry
        raise ValueError(f"Strike board entry {entry_id} not found")
