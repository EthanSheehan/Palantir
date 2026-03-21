"""Per-action autonomy policy with time-bounded grants (W4-002).

Replaces the global 3-level autonomy toggle with a per-action policy.
Each action type (FOLLOW, PAINT, INTERCEPT, etc.) gets an independent
autonomy level. Time-bounded grants auto-revert when expired.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

VALID_ACTIONS = frozenset({"FOLLOW", "PAINT", "INTERCEPT", "AUTHORIZE_COA", "ENGAGE", "SWARM_ASSIGN"})
VALID_LEVELS = frozenset({"MANUAL", "SUPERVISED", "AUTONOMOUS"})


@dataclass(frozen=True)
class ActionAutonomy:
    action: str
    level: str
    expires_at: float | None = None
    exception_targets: tuple[str, ...] = ()


class AutonomyPolicy:
    def __init__(
        self,
        default_level: str = "MANUAL",
        _actions: dict[str, ActionAutonomy] | None = None,
    ) -> None:
        if default_level not in VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(VALID_LEVELS)}, got {default_level!r}")
        self._default_level = default_level
        self._actions: dict[str, ActionAutonomy] = dict(_actions) if _actions else {}

    def set_action_level(
        self,
        action: str,
        level: str,
        duration_seconds: float | None = None,
        exception_targets: list[str] | None = None,
    ) -> AutonomyPolicy:
        if action not in VALID_ACTIONS:
            raise ValueError(f"action must be one of {sorted(VALID_ACTIONS)}, got {action!r}")
        if level not in VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(VALID_LEVELS)}, got {level!r}")

        expires_at = (time.time() + duration_seconds) if duration_seconds is not None else None
        entry = ActionAutonomy(
            action=action,
            level=level,
            expires_at=expires_at,
            exception_targets=tuple(exception_targets) if exception_targets else (),
        )
        new_actions = dict(self._actions)
        new_actions[action] = entry
        return AutonomyPolicy(default_level=self._default_level, _actions=new_actions)

    def get_action_level(self, action: str) -> str:
        entry = self._actions.get(action)
        if entry is None:
            return self._default_level
        if entry.expires_at is not None and time.time() >= entry.expires_at:
            return self._default_level
        return entry.level

    def get_effective_level(self, action: str, target_type: str | None = None) -> str:
        entry = self._actions.get(action)
        if entry is not None and target_type and target_type in entry.exception_targets:
            if entry.expires_at is None or time.time() < entry.expires_at:
                return "MANUAL"
        return self.get_action_level(action)

    def set_default_level(self, level: str) -> AutonomyPolicy:
        if level not in VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(VALID_LEVELS)}, got {level!r}")
        return AutonomyPolicy(default_level=level, _actions=self._actions)

    def is_autonomous(self, action: str, target_type: str | None = None) -> bool:
        return self.get_effective_level(action, target_type) == "AUTONOMOUS"

    def is_supervised(self, action: str, target_type: str | None = None) -> bool:
        return self.get_effective_level(action, target_type) == "SUPERVISED"

    def force_manual(self) -> AutonomyPolicy:
        return AutonomyPolicy(default_level="MANUAL")

    def to_dict(self) -> dict:
        actions = []
        for entry in self._actions.values():
            actions.append(
                {
                    "action": entry.action,
                    "level": entry.level,
                    "expires_at": entry.expires_at,
                    "exception_targets": list(entry.exception_targets),
                }
            )
        return {
            "default_level": self._default_level,
            "actions": actions,
        }

    def tick(self) -> AutonomyPolicy:
        now = time.time()
        changed = False
        new_actions: dict[str, ActionAutonomy] = {}
        for key, entry in self._actions.items():
            if entry.expires_at is not None and now >= entry.expires_at:
                changed = True
            else:
                new_actions[key] = entry
        if not changed:
            return self
        return AutonomyPolicy(default_level=self._default_level, _actions=new_actions)
