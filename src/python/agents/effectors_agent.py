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
import uuid
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
        )

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
        )

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

        result = await self._llm.complete_structured(
            messages, response_schema=schema, model_hint="fast"
        )

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
