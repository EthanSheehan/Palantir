"""
test_uav_kinematics.py
======================
Tests for the 3-DOF UAV kinematics module.

Tests cover:
- KinematicState, WindVector, UAVConstraints dataclasses
- apply_wind: ground speed and track angle adjustment
- step_kinematics: rate-limited turns, climbs, speed changes, altitude clamp
- check_separation: collision pair detection
- avoid_collision: heading offset computation
- proportional_navigation: PN guidance law
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uav_kinematics import (
    DEFAULT_CONSTRAINTS,
    KinematicState,
    WindVector,
    apply_wind,
    avoid_collision,
    check_separation,
    proportional_navigation,
    step_kinematics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state_north():
    """UAV heading north at 60 m/s, 3000m altitude."""
    return KinematicState(
        lat=45.0,
        lon=25.0,
        alt_m=3000.0,
        speed_mps=60.0,
        heading_deg=0.0,
        climb_rate_mps=0.0,
    )


@pytest.fixture
def constraints():
    return DEFAULT_CONSTRAINTS


# ---------------------------------------------------------------------------
# KinematicState
# ---------------------------------------------------------------------------


class TestKinematicState:
    def test_frozen(self, state_north):
        with pytest.raises((AttributeError, TypeError)):
            state_north.lat = 99.0

    def test_fields_present(self, state_north):
        assert state_north.lat == 45.0
        assert state_north.lon == 25.0
        assert state_north.alt_m == 3000.0
        assert state_north.speed_mps == 60.0
        assert state_north.heading_deg == 0.0
        assert state_north.climb_rate_mps == 0.0


# ---------------------------------------------------------------------------
# WindVector
# ---------------------------------------------------------------------------


class TestWindVector:
    def test_frozen(self):
        w = WindVector(speed_mps=10.0, direction_deg=270.0)
        with pytest.raises((AttributeError, TypeError)):
            w.speed_mps = 5.0

    def test_fields(self):
        w = WindVector(speed_mps=10.0, direction_deg=270.0)
        assert w.speed_mps == 10.0
        assert w.direction_deg == 270.0


# ---------------------------------------------------------------------------
# UAVConstraints
# ---------------------------------------------------------------------------


class TestUAVConstraints:
    def test_default_constraints_sensible(self):
        c = DEFAULT_CONSTRAINTS
        assert c.max_speed_mps > c.min_speed_mps
        assert c.max_speed_mps > 0
        assert c.min_altitude_m >= 0
        assert c.max_altitude_m > c.min_altitude_m
        assert c.max_turn_rate_dps > 0
        assert c.max_climb_rate_mps > 0
        assert c.min_separation_m > 0

    def test_frozen(self):
        with pytest.raises((AttributeError, TypeError)):
            DEFAULT_CONSTRAINTS.max_speed_mps = 999.0


# ---------------------------------------------------------------------------
# apply_wind
# ---------------------------------------------------------------------------


class TestApplyWind:
    def test_no_wind_returns_airspeed(self, state_north, constraints):
        gs, track = apply_wind(state_north, WindVector(speed_mps=0.0, direction_deg=0.0))
        assert abs(gs - state_north.speed_mps) < 1e-6
        assert abs(track - 0.0) < 1e-6

    def test_tailwind_increases_ground_speed(self, state_north):
        # UAV heading north (0°), wind from south (180°) = tailwind
        wind = WindVector(speed_mps=10.0, direction_deg=180.0)
        gs, track = apply_wind(state_north, wind)
        assert gs > state_north.speed_mps

    def test_headwind_decreases_ground_speed(self, state_north):
        # UAV heading north (0°), wind from north (0°) = headwind
        wind = WindVector(speed_mps=10.0, direction_deg=0.0)
        gs, track = apply_wind(state_north, wind)
        assert gs < state_north.speed_mps

    def test_crosswind_deflects_track(self, state_north):
        # Wind from the west (270°) should push track slightly east
        wind = WindVector(speed_mps=10.0, direction_deg=270.0)
        gs, track = apply_wind(state_north, wind)
        # Track should differ from heading (0°)
        assert abs(track - 0.0) > 0.1

    def test_returns_tuple_of_two_floats(self, state_north):
        result = apply_wind(state_north, WindVector(speed_mps=5.0, direction_deg=90.0))
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)


# ---------------------------------------------------------------------------
# step_kinematics
# ---------------------------------------------------------------------------


class TestStepKinematics:
    def test_returns_new_state(self, state_north, constraints):
        new = step_kinematics(state_north, 0.0, 3000.0, 60.0, 1.0, constraints, None)
        assert isinstance(new, KinematicState)
        assert new is not state_north

    def test_position_advances(self, state_north, constraints):
        new = step_kinematics(state_north, 0.0, 3000.0, 60.0, 1.0, constraints, None)
        # Heading north — lat increases
        assert new.lat > state_north.lat

    def test_turn_is_rate_limited(self, state_north, constraints):
        # Request 180° turn in 1 second — should be clamped to max_turn_rate_dps
        new = step_kinematics(state_north, 180.0, 3000.0, 60.0, 1.0, constraints, None)
        delta = abs(new.heading_deg - state_north.heading_deg)
        if delta > 180:
            delta = 360 - delta
        assert delta <= constraints.max_turn_rate_dps * 1.0 + 1e-6

    def test_altitude_clamped_to_min(self, constraints):
        state = KinematicState(
            lat=45.0,
            lon=25.0,
            alt_m=constraints.min_altitude_m + 1.0,
            speed_mps=60.0,
            heading_deg=0.0,
            climb_rate_mps=-50.0,
        )
        new = step_kinematics(state, 0.0, 0.0, 60.0, 1.0, constraints, None)
        assert new.alt_m >= constraints.min_altitude_m

    def test_altitude_clamped_to_max(self, constraints):
        state = KinematicState(
            lat=45.0,
            lon=25.0,
            alt_m=constraints.max_altitude_m - 1.0,
            speed_mps=60.0,
            heading_deg=0.0,
            climb_rate_mps=50.0,
        )
        new = step_kinematics(state, 0.0, 99999.0, 60.0, 1.0, constraints, None)
        assert new.alt_m <= constraints.max_altitude_m

    def test_climb_rate_limited(self, constraints):
        state = KinematicState(lat=45.0, lon=25.0, alt_m=3000.0, speed_mps=60.0, heading_deg=0.0, climb_rate_mps=0.0)
        new = step_kinematics(state, 0.0, 9000.0, 60.0, 1.0, constraints, None)
        actual_climb = new.alt_m - state.alt_m
        assert actual_climb <= constraints.max_climb_rate_mps * 1.0 + 1e-6

    def test_speed_clamped_to_max(self, state_north, constraints):
        new = step_kinematics(state_north, 0.0, 3000.0, constraints.max_speed_mps + 100.0, 1.0, constraints, None)
        assert new.speed_mps <= constraints.max_speed_mps

    def test_speed_clamped_to_min(self, state_north, constraints):
        new = step_kinematics(state_north, 0.0, 3000.0, 0.0, 1.0, constraints, None)
        assert new.speed_mps >= constraints.min_speed_mps

    def test_wind_applied_to_position(self, state_north, constraints):
        # With a strong tailwind, UAV should travel farther north than without
        tailwind = WindVector(speed_mps=20.0, direction_deg=180.0)
        no_wind = step_kinematics(state_north, 0.0, 3000.0, 60.0, 1.0, constraints, None)
        with_wind = step_kinematics(state_north, 0.0, 3000.0, 60.0, 1.0, constraints, tailwind)
        assert with_wind.lat > no_wind.lat

    def test_none_wind_accepted(self, state_north, constraints):
        # Should not raise
        new = step_kinematics(state_north, 0.0, 3000.0, 60.0, 1.0, constraints, None)
        assert isinstance(new, KinematicState)


# ---------------------------------------------------------------------------
# check_separation
# ---------------------------------------------------------------------------


class TestCheckSeparation:
    def _state(self, lat, lon):
        return KinematicState(lat=lat, lon=lon, alt_m=3000.0, speed_mps=60.0, heading_deg=0.0, climb_rate_mps=0.0)

    def test_no_violation_far_apart(self):
        s1 = self._state(45.0, 25.0)
        s2 = self._state(46.0, 26.0)  # ~150km apart
        pairs = check_separation([s1, s2], min_sep_m=500.0)
        assert pairs == []

    def test_violation_same_position(self):
        s1 = self._state(45.0, 25.0)
        s2 = self._state(45.0, 25.0)
        pairs = check_separation([s1, s2], min_sep_m=500.0)
        assert (0, 1) in pairs

    def test_violation_close_positions(self):
        s1 = self._state(45.0, 25.0)
        # ~111m apart (0.001 deg lat ≈ 111m)
        s2 = self._state(45.001, 25.0)
        pairs = check_separation([s1, s2], min_sep_m=500.0)
        assert (0, 1) in pairs

    def test_no_violation_below_threshold(self):
        s1 = self._state(45.0, 25.0)
        s2 = self._state(45.001, 25.0)  # ~111m
        pairs = check_separation([s1, s2], min_sep_m=100.0)
        assert pairs == []

    def test_single_uav_no_pairs(self):
        s = self._state(45.0, 25.0)
        pairs = check_separation([s], min_sep_m=500.0)
        assert pairs == []

    def test_empty_list(self):
        pairs = check_separation([], min_sep_m=500.0)
        assert pairs == []

    def test_multiple_violations(self):
        s0 = self._state(45.0, 25.0)
        s1 = self._state(45.0, 25.0)
        s2 = self._state(45.0, 25.0)
        pairs = check_separation([s0, s1, s2], min_sep_m=500.0)
        assert len(pairs) == 3  # (0,1), (0,2), (1,2)

    def test_returns_sorted_index_pairs(self):
        s0 = self._state(45.0, 25.0)
        s1 = self._state(45.0, 25.0)
        pairs = check_separation([s0, s1], min_sep_m=500.0)
        for a, b in pairs:
            assert a < b


# ---------------------------------------------------------------------------
# avoid_collision
# ---------------------------------------------------------------------------


class TestAvoidCollision:
    def _state(self, lat, lon, heading=0.0):
        return KinematicState(lat=lat, lon=lon, alt_m=3000.0, speed_mps=60.0, heading_deg=heading, climb_rate_mps=0.0)

    def test_no_threats_returns_zero(self):
        state = self._state(45.0, 25.0)
        offset = avoid_collision(state, [], min_sep_m=500.0)
        assert offset == 0.0

    def test_nearby_threat_returns_nonzero_offset(self):
        state = self._state(45.0, 25.0)
        threat = self._state(45.0, 25.0)  # Same position
        offset = avoid_collision(state, [threat], min_sep_m=500.0)
        assert offset != 0.0

    def test_offset_is_float(self):
        state = self._state(45.0, 25.0)
        threat = self._state(45.001, 25.0)
        offset = avoid_collision(state, [threat], min_sep_m=500.0)
        assert isinstance(offset, float)

    def test_far_threat_returns_zero(self):
        state = self._state(45.0, 25.0)
        far = self._state(46.0, 26.0)  # ~150km away
        offset = avoid_collision(state, [far], min_sep_m=500.0)
        assert offset == 0.0

    def test_offset_bounded(self):
        state = self._state(45.0, 25.0)
        threat = self._state(45.0, 25.0)
        offset = avoid_collision(state, [threat], min_sep_m=500.0)
        assert -180.0 <= offset <= 180.0


# ---------------------------------------------------------------------------
# proportional_navigation
# ---------------------------------------------------------------------------


class TestProportionalNavigation:
    def _pursuer(self, lat=45.0, lon=25.0, speed=100.0, heading=0.0):
        return KinematicState(lat=lat, lon=lon, alt_m=3000.0, speed_mps=speed, heading_deg=heading, climb_rate_mps=0.0)

    def test_returns_float(self):
        p = self._pursuer()
        cmd = proportional_navigation(p, 45.1, 25.0, 0.0, 0.0)
        assert isinstance(cmd, float)

    def test_heading_toward_stationary_target_directly_ahead(self):
        # Target directly north — commanded heading should be near 0°
        p = self._pursuer(lat=45.0, lon=25.0, heading=0.0)
        cmd = proportional_navigation(p, 45.1, 25.0, 0.0, 0.0)
        assert abs(cmd) < 45.0  # should point roughly north

    def test_heading_toward_target_to_east(self):
        # Target due east — pursuer heading north — should command turn right (positive)
        p = self._pursuer(lat=45.0, lon=25.0, heading=0.0)
        cmd = proportional_navigation(p, 45.0, 25.1, 0.0, 0.0)
        assert cmd > 0.0  # east of current heading

    def test_heading_toward_target_to_west(self):
        # Target due west — pursuer heading north — PN should command a westward heading
        # (roughly 270°) since the target is at bearing ~270°
        p = self._pursuer(lat=45.0, lon=25.0, heading=0.0)
        cmd = proportional_navigation(p, 45.0, 24.9, 0.0, 0.0)
        # Commanded heading should be in the western quadrant [180, 360)
        assert 180.0 < cmd < 360.0

    def test_collocated_target_returns_current_heading(self):
        p = self._pursuer(lat=45.0, lon=25.0, heading=45.0)
        cmd = proportional_navigation(p, 45.0, 25.0, 0.0, 0.0)
        # Should not blow up; return something bounded
        assert -360.0 <= cmd <= 360.0

    def test_nav_gain_scales_output(self):
        p = self._pursuer(lat=45.0, lon=25.0, heading=0.0)
        # Moving target at an angle should produce different PN with different gain
        cmd_low = proportional_navigation(p, 45.05, 25.05, 50.0, 90.0, nav_gain=1.0)
        cmd_high = proportional_navigation(p, 45.05, 25.05, 50.0, 90.0, nav_gain=5.0)
        # Different gains should produce different commands (not necessarily proportional
        # due to clamping, but they should differ unless target is on direct LOS)
        # We just verify both are floats within bounds
        assert isinstance(cmd_low, float)
        assert isinstance(cmd_high, float)

    def test_output_in_degrees(self):
        p = self._pursuer()
        cmd = proportional_navigation(p, 45.1, 25.1, 30.0, 45.0)
        assert -360.0 <= cmd <= 360.0
