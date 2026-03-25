"""
comms_sim.py
============
Communication simulation for UAV links.

Models degraded/denied comms with configurable latency, packet loss,
and bandwidth. All state is immutable (frozen dataclasses). All functions
are pure.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Enums and presets
# ---------------------------------------------------------------------------


class CommsPreset(Enum):
    FULL = "FULL"
    CONTESTED = "CONTESTED"
    DENIED = "DENIED"
    RECONNECT = "RECONNECT"


# (latency_ms, packet_loss_rate, bandwidth_kbps)
PRESET_CONFIGS: dict[CommsPreset, tuple[float, float, float]] = {
    CommsPreset.FULL: (0.0, 0.0, 1000.0),
    CommsPreset.CONTESTED: (150.0, 0.35, 200.0),
    CommsPreset.DENIED: (9999.0, 1.0, 0.0),
    CommsPreset.RECONNECT: (300.0, 0.5, 50.0),
}

_CONNECTED_PRESETS = {CommsPreset.FULL, CommsPreset.CONTESTED}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommsLink:
    drone_id: str
    preset: CommsPreset
    latency_ms: float
    packet_loss_rate: float
    bandwidth_kbps: float
    is_connected: bool


@dataclass(frozen=True)
class CommsState:
    links: dict  # drone_id -> CommsLink (use dict for JSON compat)
    pending_messages: tuple  # immutable sequence of pending message dicts


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _link_from_preset(drone_id: str, preset: CommsPreset) -> CommsLink:
    latency_ms, packet_loss_rate, bandwidth_kbps = PRESET_CONFIGS[preset]
    return CommsLink(
        drone_id=drone_id,
        preset=preset,
        latency_ms=latency_ms,
        packet_loss_rate=packet_loss_rate,
        bandwidth_kbps=bandwidth_kbps,
        is_connected=preset in _CONNECTED_PRESETS,
    )


def create_comms_state(
    drone_ids: list[str],
    preset: CommsPreset = CommsPreset.FULL,
) -> CommsState:
    links = {drone_id: _link_from_preset(drone_id, preset) for drone_id in drone_ids}
    return CommsState(links=links, pending_messages=())


# ---------------------------------------------------------------------------
# State transitions (immutable — always return new state)
# ---------------------------------------------------------------------------


def set_link_preset(state: CommsState, drone_id: str, preset: CommsPreset) -> CommsState:
    new_link = _link_from_preset(drone_id, preset)
    new_links = {**state.links, drone_id: new_link}
    return CommsState(links=new_links, pending_messages=state.pending_messages)


def degrade_all_links(state: CommsState, factor: float) -> CommsState:
    new_links = {}
    for drone_id, link in state.links.items():
        new_latency = link.latency_ms * factor
        new_loss = min(1.0, link.packet_loss_rate * factor)
        new_bw = max(0.0, link.bandwidth_kbps / factor)
        new_links[drone_id] = CommsLink(
            drone_id=link.drone_id,
            preset=link.preset,
            latency_ms=new_latency,
            packet_loss_rate=new_loss,
            bandwidth_kbps=new_bw,
            is_connected=link.is_connected and new_loss < 1.0,
        )
    return CommsState(links=new_links, pending_messages=state.pending_messages)


# ---------------------------------------------------------------------------
# Delivery simulation
# ---------------------------------------------------------------------------


def attempt_delivery(link: CommsLink, message: dict) -> tuple[bool, float]:
    """Return (delivered, delay_ms). Uses random sampling for packet loss."""
    if not link.is_connected or link.packet_loss_rate >= 1.0:
        return False, 0.0
    if link.packet_loss_rate > 0.0 and random.random() < link.packet_loss_rate:
        return False, 0.0
    return True, link.latency_ms


# ---------------------------------------------------------------------------
# Failsafe logic
# ---------------------------------------------------------------------------

_FAILSAFE_MAP: dict[CommsPreset, Optional[str]] = {
    CommsPreset.FULL: None,
    CommsPreset.CONTESTED: "OVERWATCH",
    CommsPreset.DENIED: "RTB",
    CommsPreset.RECONNECT: "OVERWATCH",
}


def get_failsafe_mode(link: CommsLink) -> Optional[str]:
    """Return recommended UAV mode when comms are degraded, or None if nominal."""
    return _FAILSAFE_MAP.get(link.preset, "RTB")
