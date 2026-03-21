"""AI Explainability Layer (W4-001) — structured rationale for every AI decision."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

_THREAT_WEIGHTS: dict[str, float] = {
    "SAM": 0.95,
    "TEL": 0.90,
    "ARTILLERY": 0.85,
    "RADAR": 0.80,
    "C2_NODE": 0.80,
    "MANPADS": 0.75,
    "APC": 0.70,
    "TRUCK": 0.50,
    "CP": 0.60,
    "LOGISTICS": 0.40,
    "UNKNOWN": 0.30,
}

_PROVIDER_LABELS: dict[str, str] = {
    "gemini": "AI: Gemini",
    "anthropic": "AI: Anthropic",
    "ollama": "AI: Ollama",
    "fallback": "Heuristic",
}


def _validate_confidence(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"confidence must be between 0.0 and 1.0, got {value}")
    return value


def _validate_top_factors(factors: list[dict]) -> list[dict]:
    if len(factors) > 3:
        raise ValueError(f"top_factors limited to 3, got {len(factors)}")
    return factors


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DecisionExplanation:
    action: str
    source: str
    confidence: float
    top_factors: list[dict]
    roe_rule_satisfied: Optional[str]
    alternatives_rejected: list[dict]
    counterfactual_threshold: Optional[str]
    timestamp: str

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)
        _validate_top_factors(self.top_factors)

    def to_dict(self) -> dict:
        return asdict(self)


def format_source_label(provider: str, model: str | None) -> str:
    base = _PROVIDER_LABELS.get(provider, provider)
    if model:
        return f"{base}: {model}"
    return base


class ExplainabilityEngine:
    def explain_nomination(
        self,
        target: dict,
        fusion_result: dict,
        roe_decision: str,
        autonomy_level: str,
    ) -> DecisionExplanation:
        target_type = target.get("target_type", "UNKNOWN")
        detection_conf = target.get("detection_confidence", 0.0)
        fusion_conf = fusion_result.get("confidence", detection_conf)
        sensor_count = fusion_result.get("sensor_count", 1)
        threat_weight = _THREAT_WEIGHTS.get(target_type, 0.3)

        confidence = min(1.0, fusion_conf * threat_weight)

        factors = [
            {"name": "target_type_threat", "weight": threat_weight, "description": f"{target_type} threat level"},
            {
                "name": "fusion_confidence",
                "weight": fusion_conf,
                "description": f"Fused confidence from {sensor_count} sensor(s)",
            },
            {
                "name": "autonomy_level",
                "weight": 0.5 if autonomy_level == "SUPERVISED" else 0.8,
                "description": f"Autonomy: {autonomy_level}",
            },
        ]

        counterfactual = None
        if confidence > 0.5:
            counterfactual = f"Confidence below {confidence - 0.2:.2f} would lower priority"

        return DecisionExplanation(
            action="NOMINATE",
            source="Heuristic: nomination_engine",
            confidence=round(confidence, 4),
            top_factors=factors[:3],
            roe_rule_satisfied=f"ROE: {roe_decision}",
            alternatives_rejected=[],
            counterfactual_threshold=counterfactual,
            timestamp=_now_iso(),
        )

    def explain_coa(
        self,
        coa: dict,
        target: dict,
        alternatives: list[dict],
        roe_decision: str,
    ) -> DecisionExplanation:
        pk = coa.get("pk_estimate", 0.0)
        time_min = coa.get("time_to_effect_min", 999.0)
        risk = coa.get("risk_score", 5.0)
        effector = coa.get("effector_name", "Unknown")

        confidence = min(1.0, pk * 0.6 + (1.0 / max(time_min, 0.01)) * 0.2 + (1.0 / max(risk, 0.01)) * 0.2)
        confidence = max(0.0, min(1.0, confidence))

        factors = [
            {"name": "pk_estimate", "weight": pk, "description": f"{effector} Pk={pk:.0%}"},
            {
                "name": "time_to_effect",
                "weight": round(1.0 / max(time_min, 0.01), 4),
                "description": f"Time: {time_min:.1f}min",
            },
            {"name": "risk_score", "weight": round(1.0 / max(risk, 0.01), 4), "description": f"Risk: {risk:.1f}/10"},
        ]

        rejected = [
            {"action": alt.get("effector_name", alt.get("id", "?")), "reason": alt.get("reason", "Not selected")}
            for alt in alternatives
        ]

        return DecisionExplanation(
            action="AUTHORIZE_COA",
            source="Heuristic: coa_ranking",
            confidence=round(confidence, 4),
            top_factors=factors[:3],
            roe_rule_satisfied=f"ROE: {roe_decision}",
            alternatives_rejected=rejected,
            counterfactual_threshold=f"Pk below {pk - 0.1:.2f} would favor alternative effector" if pk > 0.1 else None,
            timestamp=_now_iso(),
        )

    def explain_intercept(
        self,
        enemy: dict,
        drone: dict,
        threat_level: str,
    ) -> DecisionExplanation:
        fused_conf = enemy.get("fused_confidence", 0.5)
        enemy_type = enemy.get("type", "UNKNOWN")

        threat_map = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}
        threat_weight = threat_map.get(threat_level, 0.5)

        confidence = min(1.0, fused_conf * 0.6 + threat_weight * 0.4)

        factors = [
            {
                "name": "threat_level",
                "weight": threat_weight,
                "description": f"{enemy_type} classified as {threat_level}",
            },
            {
                "name": "fused_confidence",
                "weight": fused_conf,
                "description": f"Fused detection confidence: {fused_conf:.0%}",
            },
            {
                "name": "drone_availability",
                "weight": 0.8,
                "description": f"UAV-{drone.get('id', '?')} in {drone.get('mode', 'UNKNOWN')} mode",
            },
        ]

        counterfactual = (
            f"Confidence below {fused_conf - 0.15:.2f} would defer intercept"
            if fused_conf > 0.5
            else "Higher confidence needed for autonomous intercept"
        )

        return DecisionExplanation(
            action="INTERCEPT",
            source="Heuristic: intercept_logic",
            confidence=round(confidence, 4),
            top_factors=factors[:3],
            roe_rule_satisfied=None,
            alternatives_rejected=[],
            counterfactual_threshold=counterfactual,
            timestamp=_now_iso(),
        )
