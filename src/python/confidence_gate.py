"""Confidence-Gated Dynamic Authority (W4-004).

Even in AUTONOMOUS mode, escalate to operator when AI confidence is below
threshold, target is in a high-value category, or operator override rate
exceeds a configurable limit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

VIGILANCE_INTERVAL_S = 120.0


@dataclass(frozen=True)
class ConfidenceThreshold:
    action: str
    min_confidence: float
    high_value_targets: tuple[str, ...] = ()
    override_rate_limit: float = 0.3


DEFAULT_THRESHOLDS: tuple[ConfidenceThreshold, ...] = (
    ConfidenceThreshold(
        action="AUTHORIZE_COA",
        min_confidence=0.7,
        high_value_targets=("CP", "C2_NODE"),
    ),
    ConfidenceThreshold(
        action="ENGAGE",
        min_confidence=0.85,
        high_value_targets=("CP", "C2_NODE"),
    ),
    ConfidenceThreshold(
        action="INTERCEPT",
        min_confidence=0.6,
        high_value_targets=("CP", "C2_NODE"),
    ),
    ConfidenceThreshold(
        action="FOLLOW",
        min_confidence=0.3,
        high_value_targets=(),
    ),
    ConfidenceThreshold(
        action="PAINT",
        min_confidence=0.3,
        high_value_targets=(),
    ),
)


class ConfidenceGate:
    def __init__(
        self,
        thresholds: list[ConfidenceThreshold] | tuple[ConfidenceThreshold, ...],
        override_rate_limit: float = 0.3,
    ) -> None:
        self._thresholds = {t.action: t for t in thresholds}
        self._override_rate_limit = override_rate_limit
        self._override_timestamps: list[float] = []
        self._eval_timestamps: list[float] = []

    def evaluate(
        self,
        action: str,
        confidence: float,
        target_type: str | None = None,
    ) -> str:
        now = time.monotonic()
        self._eval_timestamps.append(now)

        if self._is_override_rate_exceeded(now):
            logger.warning("confidence_gate_override_rate_exceeded", action=action)
            return "ESCALATE"

        threshold = self._thresholds.get(action)
        if threshold is None:
            logger.info("confidence_gate_unknown_action", action=action)
            return "ESCALATE"

        if target_type and target_type in threshold.high_value_targets:
            logger.info(
                "confidence_gate_high_value_escalate",
                action=action,
                target_type=target_type,
            )
            return "ESCALATE"

        if confidence < threshold.min_confidence:
            logger.info(
                "confidence_gate_below_threshold",
                action=action,
                confidence=confidence,
                threshold=threshold.min_confidence,
            )
            return "ESCALATE"

        return "PROCEED"

    def record_override(self) -> None:
        self._override_timestamps.append(time.monotonic())

    def get_override_rate(self, window_seconds: float = 300.0) -> float:
        now = time.monotonic()
        cutoff = now - window_seconds
        recent_overrides = sum(1 for t in self._override_timestamps if t >= cutoff)
        recent_evals = sum(1 for t in self._eval_timestamps if t >= cutoff)
        total = recent_overrides + recent_evals
        if total == 0:
            return 0.0
        return recent_overrides / total

    def should_show_vigilance_prompt(self, seconds_since_last: float) -> bool:
        return seconds_since_last >= VIGILANCE_INTERVAL_S

    def _is_override_rate_exceeded(self, now: float) -> bool:
        cutoff = now - 300.0
        recent_overrides = sum(1 for t in self._override_timestamps if t >= cutoff)
        recent_evals = sum(1 for t in self._eval_timestamps if t >= cutoff)
        # Current eval not yet counted in total (appended before this call)
        total = recent_overrides + recent_evals
        if total == 0:
            return False
        return (recent_overrides / total) > self._override_rate_limit
