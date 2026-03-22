"""
uav_logistics.py
================
Resource constraints for UAVs: fuel depletion, ammo tracking, maintenance,
and RTB triggering.

All state is immutable (frozen dataclass). All functions are pure.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_FUEL: float = 1.0  # 100%
DEFAULT_AMMO: int = 16
RTB_THRESHOLD: float = 0.20  # trigger RTB at 20% fuel

# Fuel burn rate per second (fraction of total fuel, 0.0–1.0)
# IDLE burns least; INTERCEPT burns most.
FUEL_BURN_RATES: dict[str, float] = {
    "IDLE": 0.00001,  # ~27.8 hours to empty
    "SEARCH": 0.00005,  # ~5.6 hours to empty
    "REPOSITIONING": 0.00006,
    "RTB": 0.00006,
    "FOLLOW": 0.00008,
    "SUPPORT": 0.00008,
    "VERIFY": 0.00008,
    "OVERWATCH": 0.00008,
    "BDA": 0.00007,
    "PAINT": 0.00010,
    "INTERCEPT": 0.00015,  # ~1.85 hours to empty at full throttle
}

_DEFAULT_BURN: float = 0.00005  # fallback for unknown modes


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UAVLogistics:
    fuel_pct: float = DEFAULT_FUEL
    ammo: int = DEFAULT_AMMO
    maintenance_hours: float = 0.0


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def tick_logistics(logistics: UAVLogistics, mode: str, dt: float) -> UAVLogistics:
    """Return updated logistics after dt seconds in the given mode."""
    burn_rate = FUEL_BURN_RATES.get(mode, _DEFAULT_BURN)
    new_fuel = max(0.0, logistics.fuel_pct - burn_rate * dt)
    new_maintenance = logistics.maintenance_hours + dt / 3600.0
    return UAVLogistics(
        fuel_pct=new_fuel,
        ammo=logistics.ammo,
        maintenance_hours=new_maintenance,
    )


def needs_rtb(logistics: UAVLogistics, threshold: float = RTB_THRESHOLD) -> bool:
    """Return True if fuel is at or below the RTB threshold."""
    return logistics.fuel_pct <= threshold


def consume_ammo(logistics: UAVLogistics) -> UAVLogistics:
    """Return new logistics with ammo decremented by 1 (floor at 0)."""
    return UAVLogistics(
        fuel_pct=logistics.fuel_pct,
        ammo=max(0, logistics.ammo - 1),
        maintenance_hours=logistics.maintenance_hours,
    )


def refuel(logistics: UAVLogistics) -> UAVLogistics:
    """Return logistics with fuel and ammo fully restored (base rearm/refuel)."""
    return UAVLogistics(
        fuel_pct=DEFAULT_FUEL,
        ammo=DEFAULT_AMMO,
        maintenance_hours=logistics.maintenance_hours,
    )


def logistics_to_dict(logistics: UAVLogistics) -> dict:
    """Serialize logistics to a JSON-safe dict for get_state inclusion."""
    return {
        "fuel_pct": logistics.fuel_pct,
        "ammo": logistics.ammo,
        "maintenance_hours": logistics.maintenance_hours,
        "needs_rtb": needs_rtb(logistics),
    }
