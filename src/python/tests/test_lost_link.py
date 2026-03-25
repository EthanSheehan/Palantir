"""
Tests for lost_link.py — TDD RED phase.

Covers:
- LostLinkBehavior enum values
- LinkConfig frozen dataclass creation and defaults
- LinkStatus frozen dataclass creation
- LinkState frozen dataclass creation
- create_link_state factory
- configure_drone immutability and per-drone config
- update_contact marks last_contact_tick
- check_link_status detects lost link after timeout
- get_failsafe_action returns correct mode per behavior
- Edge cases: unknown drone_id, zero ticks, exact boundary
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from lost_link import (
    LinkConfig,
    LinkState,
    LinkStatus,
    LostLinkBehavior,
    check_link_status,
    configure_drone,
    create_link_state,
    get_failsafe_action,
    update_contact,
)

# ---------------------------------------------------------------------------
# 1. LostLinkBehavior enum
# ---------------------------------------------------------------------------


class TestLostLinkBehavior:
    def test_loiter_exists(self):
        assert LostLinkBehavior.LOITER is not None

    def test_rtb_exists(self):
        assert LostLinkBehavior.RTB is not None

    def test_safe_land_exists(self):
        assert LostLinkBehavior.SAFE_LAND is not None

    def test_continue_exists(self):
        assert LostLinkBehavior.CONTINUE is not None

    def test_all_four_behaviors_distinct(self):
        behaviors = [
            LostLinkBehavior.LOITER,
            LostLinkBehavior.RTB,
            LostLinkBehavior.SAFE_LAND,
            LostLinkBehavior.CONTINUE,
        ]
        assert len(set(behaviors)) == 4


# ---------------------------------------------------------------------------
# 2. LinkConfig dataclass
# ---------------------------------------------------------------------------


class TestLinkConfig:
    def test_link_config_is_frozen(self):
        config = LinkConfig(drone_id="uav-1", behavior=LostLinkBehavior.RTB, timeout_ticks=30)
        with pytest.raises((FrozenInstanceError, AttributeError)):
            config.timeout_ticks = 60  # type: ignore[misc]

    def test_link_config_stores_drone_id(self):
        config = LinkConfig(drone_id="alpha", behavior=LostLinkBehavior.LOITER, timeout_ticks=10)
        assert config.drone_id == "alpha"

    def test_link_config_stores_behavior(self):
        config = LinkConfig(drone_id="uav-2", behavior=LostLinkBehavior.SAFE_LAND, timeout_ticks=20)
        assert config.behavior == LostLinkBehavior.SAFE_LAND

    def test_link_config_stores_timeout(self):
        config = LinkConfig(drone_id="uav-3", behavior=LostLinkBehavior.RTB, timeout_ticks=45)
        assert config.timeout_ticks == 45

    def test_link_config_default_behavior_rtb(self):
        config = LinkConfig(drone_id="uav-1")
        assert config.behavior == LostLinkBehavior.RTB

    def test_link_config_default_timeout_30(self):
        config = LinkConfig(drone_id="uav-1")
        assert config.timeout_ticks == 30


# ---------------------------------------------------------------------------
# 3. LinkStatus dataclass
# ---------------------------------------------------------------------------


class TestLinkStatus:
    def test_link_status_is_frozen(self):
        status = LinkStatus(
            drone_id="uav-1",
            last_contact_tick=10,
            ticks_since_contact=5,
            behavior=LostLinkBehavior.RTB,
            is_link_lost=False,
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            status.is_link_lost = True  # type: ignore[misc]

    def test_link_status_stores_drone_id(self):
        status = LinkStatus(
            drone_id="bravo",
            last_contact_tick=0,
            ticks_since_contact=0,
            behavior=LostLinkBehavior.LOITER,
            is_link_lost=False,
        )
        assert status.drone_id == "bravo"

    def test_link_status_stores_last_contact_tick(self):
        status = LinkStatus(
            drone_id="uav-1",
            last_contact_tick=42,
            ticks_since_contact=3,
            behavior=LostLinkBehavior.RTB,
            is_link_lost=False,
        )
        assert status.last_contact_tick == 42

    def test_link_status_stores_ticks_since_contact(self):
        status = LinkStatus(
            drone_id="uav-1",
            last_contact_tick=10,
            ticks_since_contact=15,
            behavior=LostLinkBehavior.CONTINUE,
            is_link_lost=False,
        )
        assert status.ticks_since_contact == 15

    def test_link_status_stores_behavior(self):
        status = LinkStatus(
            drone_id="uav-1",
            last_contact_tick=0,
            ticks_since_contact=0,
            behavior=LostLinkBehavior.SAFE_LAND,
            is_link_lost=False,
        )
        assert status.behavior == LostLinkBehavior.SAFE_LAND

    def test_link_status_stores_is_link_lost(self):
        status = LinkStatus(
            drone_id="uav-1",
            last_contact_tick=0,
            ticks_since_contact=50,
            behavior=LostLinkBehavior.RTB,
            is_link_lost=True,
        )
        assert status.is_link_lost is True


# ---------------------------------------------------------------------------
# 4. create_link_state
# ---------------------------------------------------------------------------


class TestCreateLinkState:
    def test_creates_config_for_each_drone(self):
        state = create_link_state(["uav-1", "uav-2", "uav-3"])
        assert len(state.configs) == 3

    def test_creates_status_for_each_drone(self):
        state = create_link_state(["uav-1", "uav-2"])
        assert len(state.statuses) == 2

    def test_default_behavior_rtb(self):
        state = create_link_state(["uav-1"])
        assert state.configs["uav-1"].behavior == LostLinkBehavior.RTB

    def test_custom_default_behavior_applied(self):
        state = create_link_state(["uav-1", "uav-2"], default_behavior=LostLinkBehavior.LOITER)
        assert state.configs["uav-1"].behavior == LostLinkBehavior.LOITER
        assert state.configs["uav-2"].behavior == LostLinkBehavior.LOITER

    def test_empty_drone_list(self):
        state = create_link_state([])
        assert len(state.configs) == 0
        assert len(state.statuses) == 0

    def test_initial_is_link_lost_false(self):
        state = create_link_state(["uav-1"])
        assert state.statuses["uav-1"].is_link_lost is False

    def test_initial_ticks_since_contact_zero(self):
        state = create_link_state(["uav-1"])
        assert state.statuses["uav-1"].ticks_since_contact == 0

    def test_link_state_is_frozen(self):
        state = create_link_state(["uav-1"])
        with pytest.raises((FrozenInstanceError, AttributeError)):
            state.configs = {}  # type: ignore[misc]

    def test_drone_id_matches_in_config(self):
        state = create_link_state(["alpha", "bravo"])
        assert state.configs["alpha"].drone_id == "alpha"
        assert state.configs["bravo"].drone_id == "bravo"

    def test_drone_id_matches_in_status(self):
        state = create_link_state(["alpha"])
        assert state.statuses["alpha"].drone_id == "alpha"


# ---------------------------------------------------------------------------
# 5. configure_drone
# ---------------------------------------------------------------------------


class TestConfigureDrone:
    def test_returns_new_state(self):
        state = create_link_state(["uav-1"])
        new_state = configure_drone(state, "uav-1", LostLinkBehavior.LOITER)
        assert new_state is not state

    def test_original_state_unchanged(self):
        state = create_link_state(["uav-1"])
        original_behavior = state.configs["uav-1"].behavior
        configure_drone(state, "uav-1", LostLinkBehavior.SAFE_LAND)
        assert state.configs["uav-1"].behavior == original_behavior

    def test_updates_behavior(self):
        state = create_link_state(["uav-1"])
        new_state = configure_drone(state, "uav-1", LostLinkBehavior.SAFE_LAND)
        assert new_state.configs["uav-1"].behavior == LostLinkBehavior.SAFE_LAND

    def test_updates_timeout_ticks(self):
        state = create_link_state(["uav-1"])
        new_state = configure_drone(state, "uav-1", LostLinkBehavior.RTB, timeout_ticks=60)
        assert new_state.configs["uav-1"].timeout_ticks == 60

    def test_default_timeout_30(self):
        state = create_link_state(["uav-1"])
        new_state = configure_drone(state, "uav-1", LostLinkBehavior.LOITER)
        assert new_state.configs["uav-1"].timeout_ticks == 30

    def test_other_drones_unaffected(self):
        state = create_link_state(["uav-1", "uav-2"])
        new_state = configure_drone(state, "uav-1", LostLinkBehavior.SAFE_LAND)
        assert new_state.configs["uav-2"].behavior == LostLinkBehavior.RTB

    def test_can_configure_continue(self):
        state = create_link_state(["uav-1"])
        new_state = configure_drone(state, "uav-1", LostLinkBehavior.CONTINUE)
        assert new_state.configs["uav-1"].behavior == LostLinkBehavior.CONTINUE


# ---------------------------------------------------------------------------
# 6. update_contact
# ---------------------------------------------------------------------------


class TestUpdateContact:
    def test_returns_new_state(self):
        state = create_link_state(["uav-1"])
        new_state = update_contact(state, "uav-1", current_tick=5)
        assert new_state is not state

    def test_original_state_unchanged(self):
        state = create_link_state(["uav-1"])
        original_tick = state.statuses["uav-1"].last_contact_tick
        update_contact(state, "uav-1", current_tick=10)
        assert state.statuses["uav-1"].last_contact_tick == original_tick

    def test_updates_last_contact_tick(self):
        state = create_link_state(["uav-1"])
        new_state = update_contact(state, "uav-1", current_tick=42)
        assert new_state.statuses["uav-1"].last_contact_tick == 42

    def test_resets_ticks_since_contact_to_zero(self):
        state = create_link_state(["uav-1"])
        # Simulate some time passing first
        new_state = update_contact(state, "uav-1", current_tick=100)
        assert new_state.statuses["uav-1"].ticks_since_contact == 0

    def test_clears_link_lost_on_contact(self):
        state = create_link_state(["uav-1"])
        # Mark as lost first by creating a status with is_link_lost=True
        from lost_link import LinkStatus

        lost_status = LinkStatus(
            drone_id="uav-1",
            last_contact_tick=0,
            ticks_since_contact=50,
            behavior=LostLinkBehavior.RTB,
            is_link_lost=True,
        )
        # Build a state with is_link_lost=True
        state_with_lost = LinkState(
            configs=state.configs,
            statuses={**state.statuses, "uav-1": lost_status},
        )
        new_state = update_contact(state_with_lost, "uav-1", current_tick=55)
        assert new_state.statuses["uav-1"].is_link_lost is False

    def test_other_drones_unaffected(self):
        state = create_link_state(["uav-1", "uav-2"])
        original_tick_uav2 = state.statuses["uav-2"].last_contact_tick
        new_state = update_contact(state, "uav-1", current_tick=20)
        assert new_state.statuses["uav-2"].last_contact_tick == original_tick_uav2

    def test_behavior_preserved_on_update(self):
        state = create_link_state(["uav-1"])
        state = configure_drone(state, "uav-1", LostLinkBehavior.SAFE_LAND)
        new_state = update_contact(state, "uav-1", current_tick=10)
        assert new_state.statuses["uav-1"].behavior == LostLinkBehavior.SAFE_LAND


# ---------------------------------------------------------------------------
# 7. check_link_status
# ---------------------------------------------------------------------------


class TestCheckLinkStatus:
    def test_returns_link_status(self):
        state = create_link_state(["uav-1"])
        result = check_link_status(state, "uav-1", current_tick=5)
        assert isinstance(result, LinkStatus)

    def test_not_lost_when_within_timeout(self):
        state = create_link_state(["uav-1"])
        state = update_contact(state, "uav-1", current_tick=0)
        result = check_link_status(state, "uav-1", current_tick=29)
        assert result.is_link_lost is False

    def test_lost_when_at_timeout_boundary(self):
        state = create_link_state(["uav-1"])
        state = update_contact(state, "uav-1", current_tick=0)
        result = check_link_status(state, "uav-1", current_tick=30)
        assert result.is_link_lost is True

    def test_lost_when_past_timeout(self):
        state = create_link_state(["uav-1"])
        state = update_contact(state, "uav-1", current_tick=0)
        result = check_link_status(state, "uav-1", current_tick=50)
        assert result.is_link_lost is True

    def test_ticks_since_contact_calculated_correctly(self):
        state = create_link_state(["uav-1"])
        state = update_contact(state, "uav-1", current_tick=10)
        result = check_link_status(state, "uav-1", current_tick=25)
        assert result.ticks_since_contact == 15

    def test_custom_timeout_respected(self):
        state = create_link_state(["uav-1"])
        state = configure_drone(state, "uav-1", LostLinkBehavior.LOITER, timeout_ticks=10)
        state = update_contact(state, "uav-1", current_tick=0)
        result = check_link_status(state, "uav-1", current_tick=9)
        assert result.is_link_lost is False
        result2 = check_link_status(state, "uav-1", current_tick=10)
        assert result2.is_link_lost is True

    def test_behavior_from_config_in_result(self):
        state = create_link_state(["uav-1"])
        state = configure_drone(state, "uav-1", LostLinkBehavior.SAFE_LAND)
        result = check_link_status(state, "uav-1", current_tick=5)
        assert result.behavior == LostLinkBehavior.SAFE_LAND

    def test_drone_id_in_result(self):
        state = create_link_state(["uav-1"])
        result = check_link_status(state, "uav-1", current_tick=0)
        assert result.drone_id == "uav-1"

    def test_last_contact_tick_preserved_in_result(self):
        state = create_link_state(["uav-1"])
        state = update_contact(state, "uav-1", current_tick=7)
        result = check_link_status(state, "uav-1", current_tick=10)
        assert result.last_contact_tick == 7

    def test_not_lost_immediately_after_contact(self):
        state = create_link_state(["uav-1"])
        state = update_contact(state, "uav-1", current_tick=100)
        result = check_link_status(state, "uav-1", current_tick=100)
        assert result.is_link_lost is False


# ---------------------------------------------------------------------------
# 8. get_failsafe_action
# ---------------------------------------------------------------------------


class TestGetFailsafeAction:
    def _make_status(self, behavior: LostLinkBehavior, is_link_lost: bool = True) -> LinkStatus:
        return LinkStatus(
            drone_id="uav-1",
            last_contact_tick=0,
            ticks_since_contact=50,
            behavior=behavior,
            is_link_lost=is_link_lost,
        )

    def test_returns_dict(self):
        status = self._make_status(LostLinkBehavior.RTB)
        result = get_failsafe_action(status)
        assert isinstance(result, dict)

    def test_rtb_behavior_returns_rtb_action(self):
        status = self._make_status(LostLinkBehavior.RTB)
        result = get_failsafe_action(status)
        assert result.get("mode") == "RTB"

    def test_loiter_behavior_returns_search_or_loiter_mode(self):
        status = self._make_status(LostLinkBehavior.LOITER)
        result = get_failsafe_action(status)
        # LOITER maps to SEARCH (loiter pattern in the sim)
        assert result.get("mode") in ("SEARCH", "LOITER")

    def test_safe_land_behavior_returns_rtb_mode(self):
        status = self._make_status(LostLinkBehavior.SAFE_LAND)
        result = get_failsafe_action(status)
        assert result.get("mode") in ("RTB", "SAFE_LAND")

    def test_continue_behavior_returns_none_action(self):
        status = self._make_status(LostLinkBehavior.CONTINUE)
        result = get_failsafe_action(status)
        assert result.get("mode") is None or result.get("action") == "CONTINUE"

    def test_not_lost_returns_no_action(self):
        status = self._make_status(LostLinkBehavior.RTB, is_link_lost=False)
        result = get_failsafe_action(status)
        assert result.get("mode") is None

    def test_result_contains_drone_id(self):
        status = self._make_status(LostLinkBehavior.RTB)
        result = get_failsafe_action(status)
        assert result.get("drone_id") == "uav-1"

    def test_result_contains_behavior(self):
        status = self._make_status(LostLinkBehavior.LOITER)
        result = get_failsafe_action(status)
        assert "behavior" in result

    def test_rtb_action_has_drone_id(self):
        status = self._make_status(LostLinkBehavior.RTB)
        result = get_failsafe_action(status)
        assert result["drone_id"] == "uav-1"
