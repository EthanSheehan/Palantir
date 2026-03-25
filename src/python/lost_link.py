"""
lost_link.py
============
Per-drone lost-link failsafe behavior.

Tracks when telemetry was last received per drone, and triggers a
configurable failsafe action (LOITER, RTB, SAFE_LAND, CONTINUE) when
no contact is received within the configured timeout window.

All state is immutable (frozen dataclasses). All functions are pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LostLinkBehavior(Enum):
    LOITER = "LOITER"
    RTB = "RTB"
    SAFE_LAND = "SAFE_LAND"
    CONTINUE = "CONTINUE"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkConfig:
    drone_id: str
    behavior: LostLinkBehavior = LostLinkBehavior.RTB
    timeout_ticks: int = 30


@dataclass(frozen=True)
class LinkStatus:
    drone_id: str
    last_contact_tick: int
    ticks_since_contact: int
    behavior: LostLinkBehavior
    is_link_lost: bool


@dataclass(frozen=True)
class LinkState:
    configs: dict  # drone_id -> LinkConfig
    statuses: dict  # drone_id -> LinkStatus


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_link_state(
    drone_ids: list,
    default_behavior: LostLinkBehavior = LostLinkBehavior.RTB,
) -> LinkState:
    configs = {drone_id: LinkConfig(drone_id=drone_id, behavior=default_behavior) for drone_id in drone_ids}
    statuses = {
        drone_id: LinkStatus(
            drone_id=drone_id,
            last_contact_tick=0,
            ticks_since_contact=0,
            behavior=default_behavior,
            is_link_lost=False,
        )
        for drone_id in drone_ids
    }
    return LinkState(configs=configs, statuses=statuses)


# ---------------------------------------------------------------------------
# State transitions (immutable — always return new state)
# ---------------------------------------------------------------------------


def configure_drone(
    state: LinkState,
    drone_id: str,
    behavior: LostLinkBehavior,
    timeout_ticks: int = 30,
) -> LinkState:
    new_config = LinkConfig(drone_id=drone_id, behavior=behavior, timeout_ticks=timeout_ticks)
    new_configs = {**state.configs, drone_id: new_config}
    # Also update behavior in the status so they stay in sync
    existing_status = state.statuses.get(drone_id)
    if existing_status is not None:
        new_status = LinkStatus(
            drone_id=existing_status.drone_id,
            last_contact_tick=existing_status.last_contact_tick,
            ticks_since_contact=existing_status.ticks_since_contact,
            behavior=behavior,
            is_link_lost=existing_status.is_link_lost,
        )
        new_statuses = {**state.statuses, drone_id: new_status}
    else:
        new_statuses = state.statuses
    return LinkState(configs=new_configs, statuses=new_statuses)


def update_contact(state: LinkState, drone_id: str, current_tick: int) -> LinkState:
    config = state.configs.get(drone_id, LinkConfig(drone_id=drone_id))
    new_status = LinkStatus(
        drone_id=drone_id,
        last_contact_tick=current_tick,
        ticks_since_contact=0,
        behavior=config.behavior,
        is_link_lost=False,
    )
    new_statuses = {**state.statuses, drone_id: new_status}
    return LinkState(configs=state.configs, statuses=new_statuses)


# ---------------------------------------------------------------------------
# Queries (pure, no state mutation)
# ---------------------------------------------------------------------------


def check_link_status(state: LinkState, drone_id: str, current_tick: int) -> LinkStatus:
    config = state.configs.get(drone_id, LinkConfig(drone_id=drone_id))
    existing = state.statuses.get(
        drone_id,
        LinkStatus(
            drone_id=drone_id,
            last_contact_tick=0,
            ticks_since_contact=current_tick,
            behavior=config.behavior,
            is_link_lost=False,
        ),
    )
    ticks_since = current_tick - existing.last_contact_tick
    is_lost = ticks_since >= config.timeout_ticks
    return LinkStatus(
        drone_id=drone_id,
        last_contact_tick=existing.last_contact_tick,
        ticks_since_contact=ticks_since,
        behavior=config.behavior,
        is_link_lost=is_lost,
    )


_BEHAVIOR_MODE_MAP: dict[LostLinkBehavior, Optional[str]] = {
    LostLinkBehavior.LOITER: "SEARCH",
    LostLinkBehavior.RTB: "RTB",
    LostLinkBehavior.SAFE_LAND: "RTB",
    LostLinkBehavior.CONTINUE: None,
}


def get_failsafe_action(status: LinkStatus) -> dict:
    if not status.is_link_lost:
        return {"drone_id": status.drone_id, "behavior": status.behavior.value, "mode": None}
    mode = _BEHAVIOR_MODE_MAP.get(status.behavior, "RTB")
    return {
        "drone_id": status.drone_id,
        "behavior": status.behavior.value,
        "mode": mode,
        "action": status.behavior.value,
    }
