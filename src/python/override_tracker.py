"""Override Capture with Reason Codes (W4-006).

Tracks operator overrides of AI recommendations with structured reason codes.
Feeds override context into LLM prompts for within-session learning.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class OverrideReason(Enum):
    WRONG_TARGET = "WRONG_TARGET"
    WRONG_TIMING = "WRONG_TIMING"
    ROE_VIOLATION = "ROE_VIOLATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OTHER = "OTHER"


@dataclass(frozen=True)
class OverrideRecord:
    timestamp: str
    action_type: str
    target_id: int | None
    reason: OverrideReason
    free_text: str | None
    ai_recommendation: str


MAX_FREE_TEXT_LENGTH = 200


class OverrideTracker:
    def __init__(self) -> None:
        self._overrides: list[OverrideRecord] = []
        self._acceptances: list[float] = []

    def record(
        self,
        action_type: str,
        target_id: int | None,
        reason: OverrideReason,
        free_text: str | None,
        ai_recommendation: str,
    ) -> OverrideRecord:
        truncated_text = free_text[:MAX_FREE_TEXT_LENGTH] if free_text else None
        rec = OverrideRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type=action_type,
            target_id=target_id,
            reason=reason,
            free_text=truncated_text,
            ai_recommendation=ai_recommendation,
        )
        self._overrides = [*self._overrides, rec]
        return rec

    def record_acceptance(self) -> None:
        self._acceptances = [*self._acceptances, time.time()]

    def get_recent(self, count: int = 10) -> list[OverrideRecord]:
        return self._overrides[-count:] if self._overrides else []

    def get_acceptance_rate(self, window_seconds: float = 300.0) -> float:
        cutoff = time.time() - window_seconds
        recent_accepts = sum(1 for t in self._acceptances if t >= cutoff)
        recent_rejects = sum(1 for r in self._overrides if datetime.fromisoformat(r.timestamp).timestamp() >= cutoff)
        total = recent_accepts + recent_rejects
        if total == 0:
            return 1.0
        return recent_accepts / total

    def get_reason_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for r in self._overrides:
            key = r.reason.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    def get_prompt_context(self) -> str:
        rate = self.get_acceptance_rate()
        dist = self.get_reason_distribution()
        recent = self.get_recent(5)

        lines = [
            f"OPERATOR OVERRIDE CONTEXT: AI recommendation acceptance rate: {rate:.0%}.",
        ]

        if dist:
            dist_str = ", ".join(f"{k}: {v}" for k, v in sorted(dist.items(), key=lambda x: -x[1]))
            lines.append(f"Override reasons: {dist_str}.")

        if recent:
            lines.append("Recent overrides:")
            for r in recent[-3:]:
                text_part = f' ("{r.free_text}")' if r.free_text else ""
                lines.append(
                    f"  - {r.action_type} target={r.target_id} reason={r.reason.value}{text_part}"
                    f" (AI recommended: {r.ai_recommendation})"
                )

        return "\n".join(lines)
