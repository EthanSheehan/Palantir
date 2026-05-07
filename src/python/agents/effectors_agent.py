"""
Effectors Agent – Engage & Assess phases of F2T2EA.

After a COA is authorized by the operator (HITL Gate 2), this agent:
1. Simulates weapon release with time delay based on time_to_effect.
2. Rolls for hit/miss using pk_estimate (probability of kill).
3. Updates target state: ENGAGED -> DESTROYED or ESCAPED.
4. Generates a Battle Damage Assessment (BDA) report.
5. Recommends follow-on action (close track, re-engage, re-detect).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog
from llm_adapter import LLMAdapter
from schemas.ontology import CourseOfAction

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Immutable result containers
# ---------------------------------------------------------------------------

DAMAGE_DESTROYED = "DESTROYED"
DAMAGE_DAMAGED = "DAMAGED"
DAMAGE_MISSED = "MISSED"

FEEDBACK_CLOSE_TRACK = "close_track"
FEEDBACK_RE_ENGAGE = "re_engage"
FEEDBACK_RE_DETECT = "re_detect"


@dataclass(frozen=True)
class EngagementResult:
    target_id: int
    coa_id: str
    effector_used: str
    hit: bool
    damage_level: str
    bda_confidence: float
    assessment_notes: str
    reasoning_trace: str
    timestamp: str
    # Optional dict mirroring effectors.base.EffectorAck — populated when the
    # COA was dispatched through a real (mock) effector channel like AFATDS.
    effector_ack: Optional[dict] = None


# ---------------------------------------------------------------------------
# Effector routing — pick which mock stub to dispatch a COA through.
# Mirrors how Maven hands a target off to AFATDS / JREAP / JADOCS / AMPS once
# operator authorisation lands.
# ---------------------------------------------------------------------------

_AVIATION_PLATFORMS = {"F-35", "F-15E", "F-15", "F-16", "F-22", "MQ-9", "MQ-1", "AH-64", "B-21", "B-2", "B-1B"}
_ARTILLERY_PLATFORMS = {"HIMARS", "M777", "M270", "GMLRS", "ATACMS", "M109"}
_NAVAL_PLATFORMS = {"AEGIS", "SM-6", "SM-2", "NSM", "TLAM", "Tomahawk"}


def _route_effector(effector_name: str) -> str:
    """Map a COA effector name to one of AFATDS / JREAP / JADOCS / AMPS."""
    name = (effector_name or "").upper()
    if any(p in name for p in (s.upper() for s in _AVIATION_PLATFORMS)):
        return "AMPS"
    if any(p in name for p in (s.upper() for s in _ARTILLERY_PLATFORMS)):
        return "AFATDS"
    if any(p in name for p in (s.upper() for s in _NAVAL_PLATFORMS)):
        return "JREAP"
    return "JADOCS"


# ---------------------------------------------------------------------------
# Target state modifiers for pk calculation
# ---------------------------------------------------------------------------

_STATE_PK_BONUS: dict[str, float] = {
    "LOCKED": 0.10,
    "TRACKED": 0.05,
}


def _compute_modified_pk(base_pk: float, target_state: str) -> float:
    bonus = _STATE_PK_BONUS.get(target_state, 0.0)
    return min(1.0, base_pk + bonus)


def _roll_hit(modified_pk: float, rng: random.Random) -> bool:
    return rng.random() < modified_pk


def _determine_damage(hit: bool, rng: random.Random) -> str:
    if not hit:
        return DAMAGE_MISSED
    return DAMAGE_DESTROYED if rng.random() < 0.70 else DAMAGE_DAMAGED


def _determine_target_state(damage_level: str) -> str:
    if damage_level == DAMAGE_DESTROYED:
        return "DESTROYED"
    if damage_level == DAMAGE_DAMAGED:
        return "ENGAGED"
    return "ESCAPED"


# ---------------------------------------------------------------------------
# BDA prompt for LLM-assisted assessment
# ---------------------------------------------------------------------------

_BDA_SYSTEM_PROMPT = """\
You are a Battle Damage Assessment analyst. Given engagement data, produce a
concise BDA assessment. Respond with ONLY a JSON object containing:
  - "assessment_notes": string (2-3 sentence analyst assessment)
  - "bda_confidence": float 0.0-1.0 (confidence in the assessment)
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class EffectorsAgent:
    def __init__(
        self,
        llm_adapter: Optional[LLMAdapter] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self._llm = llm_adapter
        self._rng = rng if rng is not None else random.Random()

    async def execute_engagement(
        self,
        coa: CourseOfAction,
        target_data: dict,
    ) -> EngagementResult:
        target_id = target_data.get("id", 0)
        target_state = target_data.get("state", "DETECTED")
        base_pk = coa.probability_of_kill
        modified_pk = _compute_modified_pk(base_pk, target_state)

        hit = _roll_hit(modified_pk, self._rng)
        damage_level = _determine_damage(hit, self._rng)
        new_target_state = _determine_target_state(damage_level)

        # Dispatch through the appropriate mock effector channel — AFATDS for
        # tube/rocket artillery, JREAP for naval / cross-domain track relays,
        # AMPS for aviation strike packages, JADOCS for deep-fire deconfliction.
        effector_ack: Optional[dict] = None
        try:
            effector_ack = self._dispatch_effector(coa, target_data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("effector_dispatch_failed", error=str(exc), coa_id=coa.coa_id)

        logger.info(
            "engagement_executed",
            target_id=target_id,
            coa_id=coa.coa_id,
            effector=coa.effector.name,
            base_pk=base_pk,
            modified_pk=modified_pk,
            hit=hit,
            damage_level=damage_level,
            new_target_state=new_target_state,
            channel=(effector_ack.get("effector") if effector_ack else None),
        )

        # Audit-log the dispatch + engagement so the ActivityTimeline panel
        # can render real ENGAGEMENT events instead of synthetic ones.
        try:
            from audit_log import audit_log as _audit_log
            if effector_ack is not None:
                _audit_log.append(
                    action_type="effector_dispatched",
                    target_id=int(target_id) if target_id is not None else None,
                    details={**effector_ack, "coa_id": coa.coa_id},
                )
            _audit_log.append(
                action_type="engagement_executed",
                target_id=int(target_id) if target_id is not None else None,
                details={
                    "coa_id": coa.coa_id,
                    "effector": coa.effector.name,
                    "modified_pk": float(modified_pk),
                    "hit": bool(hit),
                    "damage_level": damage_level,
                    "new_target_state": new_target_state,
                    "reasoning_trace": (
                        f"Engaged target {target_id} with {coa.effector.name} "
                        f"(Pk={modified_pk:.2f}). Result: {damage_level}."
                    ),
                },
            )
        except Exception:  # noqa: BLE001
            pass

        reasoning = (
            f"Engaged target {target_id} with {coa.effector.name} "
            f"(Pk={modified_pk:.2f}, base={base_pk:.2f}, "
            f"state_bonus={_STATE_PK_BONUS.get(target_state, 0.0):.2f}). "
            f"Result: {damage_level}."
        )

        bda = await self.generate_bda(
            damage_level=damage_level,
            hit=hit,
            coa=coa,
            target_data=target_data,
        )

        return EngagementResult(
            target_id=target_id,
            coa_id=coa.coa_id,
            effector_used=coa.effector.name,
            hit=hit,
            damage_level=damage_level,
            bda_confidence=bda["bda_confidence"],
            assessment_notes=bda["assessment_notes"],
            reasoning_trace=reasoning,
            timestamp=datetime.now(timezone.utc).isoformat(),
            effector_ack=effector_ack,
        )

    def _dispatch_effector(self, coa: CourseOfAction, target_data: dict) -> dict:
        """Route the COA through the appropriate mock effector stub.

        Returns a serialisable dict version of the EffectorAck so it can be
        embedded in EngagementResult and broadcast over the WebSocket as
        EFFECTOR_ACK without the frontend needing the dataclass type.
        """
        from effectors import AfatdsStub, AmpsStub, JadocsStub, JreapStub
        from effectors.afatds import FireMissionRequest
        from effectors.amps import AviationMissionRequest
        from effectors.jadocs import DeepFireRequest
        from effectors.jreap import TrackForwardRequest

        target_id = int(target_data.get("id", 0))
        target_lat = float(target_data.get("lat", 0.0))
        target_lon = float(target_data.get("lon", 0.0))
        target_type = str(target_data.get("type", "UNKNOWN"))
        channel = _route_effector(coa.effector.name)

        if channel == "AFATDS":
            ack = AfatdsStub().dispatch(FireMissionRequest(
                target_id=target_id, target_lat=target_lat, target_lon=target_lon,
                target_type=target_type, rationale=coa.coa_id,
            ))
        elif channel == "AMPS":
            ack = AmpsStub().dispatch(AviationMissionRequest(
                target_id=target_id, target_lat=target_lat, target_lon=target_lon,
            ))
        elif channel == "JREAP":
            ack = JreapStub().dispatch(TrackForwardRequest(
                target_id=target_id, target_lat=target_lat, target_lon=target_lon,
                track_quality=12,
            ))
        else:  # JADOCS
            ack = JadocsStub().dispatch(DeepFireRequest(
                target_id=target_id, target_lat=target_lat, target_lon=target_lon,
            ))

        return {
            "effector": ack.effector,
            "accepted": ack.accepted,
            "mission_id": ack.mission_id,
            "sent_at_ms": ack.sent_at_ms,
            "ack_at_ms": ack.ack_at_ms,
            "latency_ms": ack.latency_ms,
            "detail": ack.detail,
            "nato_msg_id": ack.nato_msg_id,
            "channel": channel,
        }

    async def generate_bda(
        self,
        damage_level: str,
        hit: bool,
        coa: CourseOfAction,
        target_data: dict,
    ) -> dict:
        if self._llm is not None and self._llm.is_available():
            return await self._generate_bda_llm(damage_level, hit, coa, target_data)
        return self._generate_bda_heuristic(damage_level, hit, coa, target_data)

    def _generate_bda_heuristic(
        self,
        damage_level: str,
        hit: bool,
        coa: CourseOfAction,
        target_data: dict,
    ) -> dict:
        target_type = target_data.get("type", "UNKNOWN")

        if damage_level == DAMAGE_DESTROYED:
            notes = (
                f"{target_type} target confirmed destroyed by {coa.effector.name}. "
                f"Post-strike assessment indicates complete neutralization. "
                f"No further engagement required."
            )
            confidence = 0.90
        elif damage_level == DAMAGE_DAMAGED:
            notes = (
                f"{target_type} target damaged by {coa.effector.name}. "
                f"Partial effect observed; target may retain limited capability. "
                f"Re-engagement recommended."
            )
            confidence = 0.70
        else:
            notes = (
                f"{target_type} target missed by {coa.effector.name}. "
                f"No observable damage. Target likely displaced from last known position. "
                f"Re-detection via ISR recommended."
            )
            confidence = 0.50

        return {"assessment_notes": notes, "bda_confidence": confidence}

    async def _generate_bda_llm(
        self,
        damage_level: str,
        hit: bool,
        coa: CourseOfAction,
        target_data: dict,
    ) -> dict:
        messages = [
            {"role": "system", "content": _BDA_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Engagement data:\n"
                    f"- Effector: {coa.effector.name}\n"
                    f"- Target type: {target_data.get('type', 'UNKNOWN')}\n"
                    f"- Hit: {hit}\n"
                    f"- Damage level: {damage_level}\n"
                    f"- Pk used: {coa.probability_of_kill}\n"
                    f"Produce BDA assessment."
                ),
            },
        ]

        schema = {
            "type": "object",
            "properties": {
                "assessment_notes": {"type": "string"},
                "bda_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["assessment_notes", "bda_confidence"],
        }

        result = await self._llm.complete_structured(messages, response_schema=schema, model_hint="fast")

        if not result:
            logger.warning("bda_llm_fallback", reason="empty LLM response")
            return self._generate_bda_heuristic(damage_level, hit, coa, target_data)

        return {
            "assessment_notes": result.get("assessment_notes", "LLM assessment unavailable."),
            "bda_confidence": float(result.get("bda_confidence", 0.5)),
        }

    def get_feedback_recommendation(self, result: EngagementResult) -> dict:
        if result.damage_level == DAMAGE_DESTROYED:
            return {
                "action": FEEDBACK_CLOSE_TRACK,
                "target_id": result.target_id,
                "reason": "Target confirmed destroyed. Closing track.",
                "new_target_state": "DESTROYED",
            }

        if result.damage_level == DAMAGE_DAMAGED:
            return {
                "action": FEEDBACK_RE_ENGAGE,
                "target_id": result.target_id,
                "reason": "Target damaged but not destroyed. New COA required.",
                "new_target_state": "ENGAGED",
            }

        return {
            "action": FEEDBACK_RE_DETECT,
            "target_id": result.target_id,
            "reason": "Target missed and likely displaced. ISR re-detection needed.",
            "new_target_state": "ESCAPED",
        }
