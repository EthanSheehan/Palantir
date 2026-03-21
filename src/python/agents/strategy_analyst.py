"""
agents/strategy_analyst.py
==========================
Strategy Analyst Agent — evaluates ISR detections against ROE,
performs decision-gap analysis, assigns priority scores, and
hands off actionable targets to the Strike Board.

Supports both LLM-enhanced and heuristic evaluation paths.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import structlog
from core.ontology import (
    Detection,
    FriendlyForce,
    IdentityClassification,
    Location,
)
from core.state import AnalystState
from llm_adapter import LLMAdapter, LLMResponse
from schemas.ontology import (
    EngagementDecision,
    ISRObserverOutput,
    StrategyAnalystOutput,
    TargetNomination,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HEURISTIC_PRIORITY: dict[str, int] = {
    "SAM": 9,
    "TEL": 8,
    "RADAR": 7,
    "CP": 6,
    "C2_NODE": 6,
    "MANPADS": 5,
    "TRUCK": 3,
    "LOGISTICS": 3,
}

_DEFAULT_PRIORITY = 4

_STRATEGY_ANALYST_PROMPT = """You are the Strategy Analyst Agent in a military C2 kill chain.
Given a target detection and Rules of Engagement, evaluate whether the target should be
nominated for engagement, monitored, or ignored.

Consider:
1. Target type and threat level
2. ROE compliance (confidence thresholds, proximity to friendlies)
3. Collateral damage risk
4. Tactical value of engagement vs. continued monitoring

Respond with valid JSON:
{{
  "priority_score": <1-10 integer>,
  "roe_compliant": <true/false>,
  "recommendation": "NOMINATE|MONITOR|IGNORE",
  "collateral_risk": "LOW|MEDIUM|HIGH",
  "reasoning_trace": "<detailed explanation of the decision>"
}}

Target Data:
{target_json}

ROE Context:
{roe_json}"""


# ---------------------------------------------------------------------------
# Immutable evaluation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetEvaluation:
    priority_score: int
    roe_compliant: bool
    recommendation: str
    collateral_risk: str
    reasoning_trace: str


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _haversine_m(a: Location, b: Location) -> float:
    R = 6_371_000
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _nearest_friendly(
    det: Detection,
    friendlies: list[FriendlyForce],
) -> tuple[str, float]:
    if not friendlies:
        return ("none", float("inf"))

    best_id = friendlies[0].id
    best_dist = _haversine_m(det.location, friendlies[0].location)
    for ff in friendlies[1:]:
        d = _haversine_m(det.location, ff.location)
        if d < best_dist:
            best_id = ff.id
            best_dist = d
    return best_id, best_dist


def _compute_priority(
    det: Detection,
    nearest_dist_m: float,
) -> int:
    identity_weight = {
        IdentityClassification.HOSTILE: 4.0,
        IdentityClassification.SUSPECT: 2.5,
        IdentityClassification.UNKNOWN: 1.5,
        IdentityClassification.NEUTRAL: 0.5,
        IdentityClassification.FRIENDLY: 0.0,
    }.get(det.identity, 1.0)

    confidence_factor = det.confidence * 3.0
    proximity_factor = max(0.0, 3.0 * (1.0 - nearest_dist_m / 5000.0))

    raw = identity_weight + confidence_factor + proximity_factor
    return max(1, min(10, round(raw)))


def _heuristic_priority_for_type(target_type: str) -> int:
    return _HEURISTIC_PRIORITY.get(target_type, _DEFAULT_PRIORITY)


def _heuristic_reasoning(target_type: str, priority: int) -> str:
    if priority >= 8:
        return (
            f"Target type '{target_type}' is a high-threat system "
            f"(priority {priority}/10). Immediate engagement recommended."
        )
    if priority >= 6:
        return (
            f"Target type '{target_type}' is a moderate-threat system "
            f"(priority {priority}/10). Nomination for strike board review."
        )
    if priority >= 4:
        return (
            f"Target type '{target_type}' is a low-priority target "
            f"(priority {priority}/10). Continued monitoring advised."
        )
    return f"Target type '{target_type}' is minimal threat (priority {priority}/10). No action required."


def _recommendation_for_priority(priority: int) -> str:
    if priority >= 7:
        return "NOMINATE"
    if priority >= 4:
        return "MONITOR"
    return "IGNORE"


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------


class StrategyAnalystAgent:
    def __init__(
        self,
        llm_client: Any = None,
        llm_adapter: LLMAdapter | None = None,
    ):
        self.llm_client = llm_client
        self.llm_adapter = llm_adapter

    def evaluate_tracks(self, isr_output: ISRObserverOutput) -> StrategyAnalystOutput:
        nominations: list[TargetNomination] = []
        for track in isr_output.tracks:
            evaluation = self._evaluate_track_heuristic(
                track.classification.value,
                track.confidence,
            )
            decision = _decision_from_recommendation(evaluation.recommendation)

            nominations.append(
                TargetNomination(
                    track_id=track.track_id,
                    decision=decision,
                    roe_compliance=evaluation.roe_compliant,
                    collateral_risk=evaluation.collateral_risk,
                    reasoning=evaluation.reasoning_trace,
                )
            )

        nominated_count = sum(1 for n in nominations if n.decision == EngagementDecision.NOMINATE)
        return StrategyAnalystOutput(
            nominations=nominations,
            summary=(f"Evaluated {len(isr_output.tracks)} tracks. {nominated_count} nominated."),
        )

    async def evaluate_target(
        self,
        target_data: dict[str, Any],
        roe_context: dict[str, Any] | None = None,
    ) -> TargetEvaluation:
        if not self.llm_adapter or not self.llm_adapter.is_available():
            logger.info("strategy_llm_unavailable_falling_back_to_heuristic")
            return self._evaluate_target_heuristic(target_data)

        roe_json = json.dumps(roe_context or {}, indent=2)
        target_json = json.dumps(target_data, indent=2)

        prompt = _STRATEGY_ANALYST_PROMPT.format(
            target_json=target_json,
            roe_json=roe_json,
        )
        messages = [
            {"role": "user", "content": prompt},
        ]

        try:
            response: LLMResponse = await self.llm_adapter.complete(
                messages,
                model_hint="reasoning",
            )

            if response.provider == "fallback":
                logger.info("strategy_llm_returned_fallback")
                return self._evaluate_target_heuristic(target_data)

            return self._parse_llm_evaluation(response.content, target_data)
        except Exception as exc:
            logger.error("strategy_llm_processing_failed", error=str(exc))
            return self._evaluate_target_heuristic(target_data)

    def _parse_llm_evaluation(
        self,
        content: str,
        target_data: dict[str, Any],
    ) -> TargetEvaluation:
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            logger.warning(
                "strategy_llm_json_parse_failed",
                content_preview=content[:200],
            )
            return self._evaluate_target_heuristic(target_data)

        priority = max(1, min(10, int(parsed.get("priority_score", 5))))
        roe_compliant = bool(parsed.get("roe_compliant", True))
        recommendation = parsed.get("recommendation", "MONITOR")
        collateral_risk = parsed.get("collateral_risk", "LOW")
        reasoning = parsed.get("reasoning_trace", "")

        if recommendation not in ("NOMINATE", "MONITOR", "IGNORE"):
            recommendation = _recommendation_for_priority(priority)

        logger.info(
            "strategy_llm_evaluation",
            target_type=target_data.get("type"),
            priority=priority,
            recommendation=recommendation,
            reasoning=reasoning,
        )

        return TargetEvaluation(
            priority_score=priority,
            roe_compliant=roe_compliant,
            recommendation=recommendation,
            collateral_risk=collateral_risk,
            reasoning_trace=reasoning,
        )

    def _evaluate_target_heuristic(
        self,
        target_data: dict[str, Any],
    ) -> TargetEvaluation:
        target_type = target_data.get("type", "Unknown")
        priority = _heuristic_priority_for_type(target_type)
        recommendation = _recommendation_for_priority(priority)
        reasoning = _heuristic_reasoning(target_type, priority)

        logger.info(
            "strategy_heuristic_evaluation",
            target_type=target_type,
            priority=priority,
            recommendation=recommendation,
            reasoning=reasoning,
        )

        return TargetEvaluation(
            priority_score=priority,
            roe_compliant=True,
            recommendation=recommendation,
            collateral_risk="LOW",
            reasoning_trace=reasoning,
        )

    def _evaluate_track_heuristic(
        self,
        classification: str,
        confidence: float,
    ) -> TargetEvaluation:
        priority = _heuristic_priority_for_type(classification)
        recommendation = _recommendation_for_priority(priority)
        reasoning = _heuristic_reasoning(classification, priority)

        return TargetEvaluation(
            priority_score=priority,
            roe_compliant=True,
            recommendation=recommendation,
            collateral_risk="LOW",
            reasoning_trace=reasoning,
        )

    async def nominate_to_strike_board(
        self,
        target: dict[str, Any],
        evaluation: TargetEvaluation,
    ) -> dict[str, Any]:
        return {
            "target_id": target.get("id", "unknown"),
            "target_type": target.get("type", "Unknown"),
            "lat": target.get("lat", 0.0),
            "lon": target.get("lon", 0.0),
            "priority_score": evaluation.priority_score,
            "roe_compliant": evaluation.roe_compliant,
            "recommendation": evaluation.recommendation,
            "collateral_risk": evaluation.collateral_risk,
            "reasoning": evaluation.reasoning_trace,
            "status": "PENDING_HITL_REVIEW",
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _decision_from_recommendation(recommendation: str) -> EngagementDecision:
    mapping = {
        "NOMINATE": EngagementDecision.NOMINATE,
        "MONITOR": EngagementDecision.MONITOR,
        "IGNORE": EngagementDecision.REJECT,
    }
    return mapping.get(recommendation, EngagementDecision.MONITOR)


# ---------------------------------------------------------------------------
# LangGraph node (backward compatibility)
# ---------------------------------------------------------------------------


def evaluate_detections(state: AnalystState) -> dict[str, Any]: ...
