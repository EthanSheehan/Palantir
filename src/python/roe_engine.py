"""ROE (Rules of Engagement) Engine — deterministic rule-based veto layer (W3-001).

Provides formal declarative ROE rules with unconditional veto power in AUTONOMOUS mode.
Rules are evaluated in order; first DENIED wins. If no rule matches, default is ESCALATE.
"""

from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog
import yaml

logger = structlog.get_logger(__name__)

AUTONOMY_RANK: dict[str, int] = {
    "MANUAL": 0,
    "SUPERVISED": 1,
    "AUTONOMOUS": 2,
}


class ROEDecision(Enum):
    PERMITTED = "PERMITTED"
    DENIED = "DENIED"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class ROERule:
    name: str
    decision: ROEDecision
    target_type: Optional[str] = None
    zone_id: Optional[str] = None
    min_autonomy_level: Optional[str] = None
    max_collateral_radius_m: Optional[float] = None


@dataclass(frozen=True)
class ROEChangeEntry:
    timestamp: float
    action: str
    rule_before: Optional[ROERule]
    rule_after: Optional[ROERule]


class ROEChangeLog:
    """Append-only log of ROE rule changes."""

    def __init__(self) -> None:
        self._entries: list[ROEChangeEntry] = []

    def record(
        self,
        action: str,
        *,
        rule_before: ROERule | None,
        rule_after: ROERule | None,
    ) -> None:
        entry = ROEChangeEntry(
            timestamp=time.time(),
            action=action,
            rule_before=rule_before,
            rule_after=rule_after,
        )
        self._entries.append(entry)

    @property
    def entries(self) -> list[ROEChangeEntry]:
        return list(self._entries)


def _zone_matches(rule_zone: str | None, target_zone: str | None) -> bool:
    if rule_zone is None:
        return True
    if target_zone is None:
        return False
    return fnmatch.fnmatch(target_zone, rule_zone)


def _autonomy_matches(rule_min: str | None, actual: str) -> bool:
    if rule_min is None:
        return True
    return AUTONOMY_RANK.get(actual, 0) >= AUTONOMY_RANK.get(rule_min, 0)


def _collateral_matches(rule_max: float | None, actual: float) -> bool:
    if rule_max is None:
        return True
    return actual <= rule_max


def _target_type_matches(rule_type: str | None, actual: str) -> bool:
    if rule_type is None:
        return True
    return rule_type == actual


def _rule_matches(
    rule: ROERule,
    target_type: str,
    zone_id: str | None,
    autonomy_level: str,
    collateral_radius_m: float,
) -> bool:
    return (
        _target_type_matches(rule.target_type, target_type)
        and _zone_matches(rule.zone_id, zone_id)
        and _autonomy_matches(rule.min_autonomy_level, autonomy_level)
        and _collateral_matches(rule.max_collateral_radius_m, collateral_radius_m)
    )


class ROEEngine:
    """Deterministic rule-based ROE evaluator.

    Rules are evaluated in order. First DENIED wins unconditionally.
    If no DENIED matches, the first matching PERMITTED or ESCALATE is returned.
    If no rule matches at all, default is ESCALATE.
    """

    def __init__(self, rules: list[ROERule]) -> None:
        self._rules = tuple(rules)

    @property
    def rules(self) -> tuple[ROERule, ...]:
        return self._rules

    def evaluate(
        self,
        target_type: str,
        zone_id: str | None,
        autonomy_level: str,
        collateral_radius_m: float = 0.0,
    ) -> ROEDecision:
        matched: list[ROEDecision] = []
        for rule in self._rules:
            if _rule_matches(rule, target_type, zone_id, autonomy_level, collateral_radius_m):
                if rule.decision == ROEDecision.DENIED:
                    logger.debug("roe_denied", rule=rule.name, target_type=target_type, zone_id=zone_id)
                    return ROEDecision.DENIED
                matched.append(rule.decision)

        if matched:
            return matched[0]

        return ROEDecision.ESCALATE

    @classmethod
    def load_from_yaml(cls, path: str) -> ROEEngine:
        with open(path) as f:
            data = yaml.safe_load(f)

        raw_rules = data.get("rules", [])
        rules: list[ROERule] = []
        for raw in raw_rules:
            try:
                decision = ROEDecision(raw["decision"])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Invalid ROE rule decision in {path}: {raw.get('decision')!r}") from exc

            rules.append(
                ROERule(
                    name=raw.get("name", "unnamed"),
                    decision=decision,
                    target_type=raw.get("target_type"),
                    zone_id=raw.get("zone_id"),
                    min_autonomy_level=raw.get("min_autonomy_level"),
                    max_collateral_radius_m=raw.get("max_collateral_radius_m"),
                )
            )

        logger.info("roe_loaded", path=path, rule_count=len(rules))
        return cls(rules)
