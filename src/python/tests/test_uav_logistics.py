"""
Tests for uav_logistics.py — TDD RED phase.

All tests must fail before uav_logistics.py is implemented.
Uses no sim_engine dependency — pure unit tests for logistics functions.
"""

from dataclasses import FrozenInstanceError

import pytest

# ---------------------------------------------------------------------------
# Imports (will fail until implementation exists)
# ---------------------------------------------------------------------------
from uav_logistics import (
    DEFAULT_AMMO,
    FUEL_BURN_RATES,
    RTB_THRESHOLD,
    UAVLogistics,
    consume_ammo,
    needs_rtb,
    tick_logistics,
)

# ---------------------------------------------------------------------------
# 1. Initial state
# ---------------------------------------------------------------------------


def test_initial_fuel_at_100():
    logistics = UAVLogistics()
    assert logistics.fuel_pct == 1.0


def test_initial_ammo_at_default():
    logistics = UAVLogistics()
    assert logistics.ammo == DEFAULT_AMMO
    assert logistics.ammo > 0


def test_initial_maintenance_hours_zero():
    logistics = UAVLogistics()
    assert logistics.maintenance_hours == 0.0


def test_logistics_is_frozen():
    logistics = UAVLogistics()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        logistics.fuel_pct = 0.5


# ---------------------------------------------------------------------------
# 2. Fuel depletion rates by mode
# ---------------------------------------------------------------------------


def test_fuel_burn_rates_defined_for_all_modes():
    required_modes = {
        "IDLE",
        "SEARCH",
        "FOLLOW",
        "PAINT",
        "INTERCEPT",
        "SUPPORT",
        "VERIFY",
        "OVERWATCH",
        "BDA",
        "REPOSITIONING",
        "RTB",
    }
    for mode in required_modes:
        assert mode in FUEL_BURN_RATES, f"Missing burn rate for mode {mode}"


def test_idle_burns_less_than_search():
    assert FUEL_BURN_RATES["IDLE"] < FUEL_BURN_RATES["SEARCH"]


def test_search_burns_less_than_follow():
    assert FUEL_BURN_RATES["SEARCH"] < FUEL_BURN_RATES["FOLLOW"]


def test_follow_burns_less_than_intercept():
    assert FUEL_BURN_RATES["FOLLOW"] < FUEL_BURN_RATES["INTERCEPT"]


def test_tick_logistics_depletes_fuel_in_search():
    logistics = UAVLogistics(fuel_pct=1.0)
    updated = tick_logistics(logistics, mode="SEARCH", dt=1.0)
    assert updated.fuel_pct < 1.0


def test_tick_logistics_intercept_burns_more_than_search():
    logistics = UAVLogistics(fuel_pct=1.0)
    dt = 10.0
    after_search = tick_logistics(logistics, mode="SEARCH", dt=dt)
    after_intercept = tick_logistics(logistics, mode="INTERCEPT", dt=dt)
    assert after_intercept.fuel_pct < after_search.fuel_pct


def test_tick_logistics_idle_burns_minimum():
    logistics = UAVLogistics(fuel_pct=1.0)
    updated = tick_logistics(logistics, mode="IDLE", dt=1.0)
    # IDLE burns the least — fuel decreases but by the minimum rate
    burn = 1.0 - updated.fuel_pct
    assert burn == pytest.approx(FUEL_BURN_RATES["IDLE"] * 1.0)


def test_tick_logistics_fuel_never_below_zero():
    logistics = UAVLogistics(fuel_pct=0.001)
    updated = tick_logistics(logistics, mode="INTERCEPT", dt=100.0)
    assert updated.fuel_pct >= 0.0


def test_tick_logistics_returns_new_instance():
    logistics = UAVLogistics(fuel_pct=1.0)
    updated = tick_logistics(logistics, mode="SEARCH", dt=1.0)
    assert updated is not logistics
    assert logistics.fuel_pct == 1.0  # original unchanged


# ---------------------------------------------------------------------------
# 3. RTB threshold logic
# ---------------------------------------------------------------------------


def test_needs_rtb_false_at_full_fuel():
    logistics = UAVLogistics(fuel_pct=1.0)
    assert needs_rtb(logistics) is False


def test_needs_rtb_false_above_threshold():
    logistics = UAVLogistics(fuel_pct=RTB_THRESHOLD + 0.05)
    assert needs_rtb(logistics) is False


def test_needs_rtb_true_at_threshold():
    logistics = UAVLogistics(fuel_pct=RTB_THRESHOLD)
    assert needs_rtb(logistics) is True


def test_needs_rtb_true_below_threshold():
    logistics = UAVLogistics(fuel_pct=0.05)
    assert needs_rtb(logistics) is True


def test_needs_rtb_custom_threshold():
    logistics = UAVLogistics(fuel_pct=0.35)
    assert needs_rtb(logistics, threshold=0.4) is True
    assert needs_rtb(logistics, threshold=0.3) is False


# ---------------------------------------------------------------------------
# 4. Ammo decrement
# ---------------------------------------------------------------------------


def test_consume_ammo_decrements_by_one():
    logistics = UAVLogistics(ammo=10)
    updated = consume_ammo(logistics)
    assert updated.ammo == 9


def test_consume_ammo_returns_new_instance():
    logistics = UAVLogistics(ammo=10)
    updated = consume_ammo(logistics)
    assert updated is not logistics
    assert logistics.ammo == 10  # original unchanged


def test_consume_ammo_at_zero_stays_zero():
    logistics = UAVLogistics(ammo=0)
    updated = consume_ammo(logistics)
    assert updated.ammo == 0


def test_zero_ammo_detected():
    logistics = UAVLogistics(ammo=0)
    assert logistics.ammo == 0


# ---------------------------------------------------------------------------
# 5. Fuel recovery at base (RTB complete)
# ---------------------------------------------------------------------------


def test_fuel_recovery_at_base():
    from uav_logistics import refuel

    logistics = UAVLogistics(fuel_pct=0.1)
    refueled = refuel(logistics)
    assert refueled.fuel_pct == 1.0


def test_refuel_restores_ammo():
    from uav_logistics import refuel

    logistics = UAVLogistics(fuel_pct=0.1, ammo=0)
    refueled = refuel(logistics)
    assert refueled.ammo == DEFAULT_AMMO


def test_refuel_returns_new_instance():
    from uav_logistics import refuel

    logistics = UAVLogistics(fuel_pct=0.1, ammo=3)
    refueled = refuel(logistics)
    assert refueled is not logistics
    assert logistics.fuel_pct == 0.1  # original unchanged


# ---------------------------------------------------------------------------
# 6. Serialization for get_state
# ---------------------------------------------------------------------------


def test_logistics_to_dict():
    from uav_logistics import logistics_to_dict

    logistics = UAVLogistics(fuel_pct=0.75, ammo=8, maintenance_hours=12.5)
    d = logistics_to_dict(logistics)
    assert d["fuel_pct"] == pytest.approx(0.75)
    assert d["ammo"] == 8
    assert d["maintenance_hours"] == pytest.approx(12.5)
    assert d["needs_rtb"] is False


def test_logistics_to_dict_flags_rtb():
    from uav_logistics import logistics_to_dict

    logistics = UAVLogistics(fuel_pct=RTB_THRESHOLD - 0.01)
    d = logistics_to_dict(logistics)
    assert d["needs_rtb"] is True


# ---------------------------------------------------------------------------
# 7. Maintenance accumulation
# ---------------------------------------------------------------------------


def test_tick_logistics_increments_maintenance_hours():
    logistics = UAVLogistics(maintenance_hours=0.0)
    dt_sec = 3600.0  # 1 hour
    updated = tick_logistics(logistics, mode="SEARCH", dt=dt_sec)
    assert updated.maintenance_hours == pytest.approx(1.0)


def test_maintenance_hours_accumulate_over_multiple_ticks():
    logistics = UAVLogistics(maintenance_hours=0.0)
    for _ in range(4):
        logistics = tick_logistics(logistics, mode="IDLE", dt=3600.0)
    assert logistics.maintenance_hours == pytest.approx(4.0)
