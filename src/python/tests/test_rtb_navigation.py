"""Tests for RTB mode real return navigation (W1-022).

TDD: Write tests first, run to confirm RED, then implement.
"""
import math
import sys
from pathlib import Path
import pytest

_SRC = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _SRC)

from sim_engine import UAV, MAX_TURN_RATE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uav(x: float, y: float, home_x: float = 25.0, home_y: float = 45.5) -> UAV:
    """Create a UAV with home_position set, placed at (x, y), pointing toward home."""
    uav = UAV(id=1, x=x, y=y, zone_id=(0, 0))
    uav.home_position = (home_x, home_y)
    uav.mode = "RTB"
    # Point roughly toward home so turn-rate tests are meaningful
    dx, dy = home_x - x, home_y - y
    dist = math.hypot(dx, dy) or 1.0
    speed = 0.05
    uav.vx = (dx / dist) * speed
    uav.vy = (dy / dist) * speed
    return uav


ARRIVAL_KM = 0.5      # expected threshold (half a km)
DEG_PER_KM = 1.0 / 111.0
ARRIVAL_DEG = ARRIVAL_KM * DEG_PER_KM   # ~0.0045 deg


# ---------------------------------------------------------------------------
# Test 1 — drone navigates TOWARD home
# ---------------------------------------------------------------------------

class TestRtbNavigatesTowardHome:
    def test_rtb_moves_drone_closer_to_home_each_tick(self):
        """After several ticks, a drone far from home should be closer."""
        home_x, home_y = 25.0, 45.5
        # Place drone 0.5 degrees away (~55km), pointing toward home
        uav = _make_uav(x=25.5, y=46.0, home_x=home_x, home_y=home_y)
        speed = 0.05
        dt = 1.0

        dist_before = math.hypot(uav.x - home_x, uav.y - home_y)

        # Run 30 ticks — drone pointing toward home should converge
        for _ in range(30):
            uav.update(dt, speed)

        dist_after = math.hypot(uav.x - home_x, uav.y - home_y)

        assert dist_after < dist_before, (
            f"Drone should have moved closer to home after 30 ticks. "
            f"Before: {dist_before:.4f}, After: {dist_after:.4f}"
        )

    def test_rtb_mode_stays_rtb_while_far_from_home(self):
        """Drone should remain in RTB mode while still far from home."""
        home_x, home_y = 25.0, 45.5
        uav = _make_uav(x=25.5, y=46.0, home_x=home_x, home_y=home_y)
        speed = 0.05
        dt = 1.0

        for _ in range(5):
            uav.update(dt, speed)

        assert uav.mode == "RTB", "Drone should remain in RTB mode while far from home"


# ---------------------------------------------------------------------------
# Test 2 — turn_toward used (smooth arcs, no teleporting)
# ---------------------------------------------------------------------------

class TestRtbUsesTurnToward:
    def test_rtb_does_not_teleport_heading(self):
        """Heading should change gradually (max 3x MAX_TURN_RATE * dt per tick)."""
        home_x, home_y = 25.0, 45.5
        # Place drone pointing mostly away from home (90 degrees off) so turn is needed
        uav = _make_uav(x=25.5, y=46.0, home_x=home_x, home_y=home_y)
        # Override velocity to point perpendicular to home direction
        uav.vx = 0.05
        uav.vy = 0.0
        speed = 0.05
        dt = 1.0

        heading_before = math.atan2(uav.vx, uav.vy)
        uav.update(dt, speed)
        heading_after = math.atan2(uav.vx, uav.vy)

        delta = abs(heading_after - heading_before)
        # Normalize to [0, pi]
        while delta > math.pi:
            delta = abs(delta - 2 * math.pi)

        # Delta should not exceed 3x MAX_TURN_RATE * dt (same multiplier used internally)
        max_allowed = MAX_TURN_RATE * dt * 3 + 1e-9
        assert delta <= max_allowed, (
            f"Heading change {math.degrees(delta):.2f}° exceeds max allowed "
            f"{math.degrees(max_allowed):.2f}°. Drone teleported heading."
        )

    def test_rtb_velocity_magnitude_near_cruise_speed(self):
        """After RTB navigation, speed should remain close to cruise speed."""
        home_x, home_y = 25.0, 45.5
        uav = _make_uav(x=25.5, y=46.0, home_x=home_x, home_y=home_y)
        speed = 0.05
        dt = 1.0

        for _ in range(10):
            uav.update(dt, speed)

        actual_speed = math.hypot(uav.vx, uav.vy)
        assert abs(actual_speed - speed) < speed * 0.05, (
            f"Speed {actual_speed:.4f} deviates too much from cruise {speed}. "
            "RTB should maintain cruise speed."
        )


# ---------------------------------------------------------------------------
# Test 3 — transitions to IDLE on arrival
# ---------------------------------------------------------------------------

class TestRtbTransitionsToIdleOnArrival:
    def test_rtb_transitions_to_idle_when_within_threshold(self):
        """Drone within arrival threshold should immediately switch to IDLE."""
        home_x, home_y = 25.0, 45.5
        # Place drone just inside the arrival threshold
        tiny_offset = ARRIVAL_DEG * 0.3   # well inside threshold
        uav = _make_uav(x=home_x + tiny_offset, y=home_y, home_x=home_x, home_y=home_y)
        speed = 0.05
        dt = 1.0

        uav.update(dt, speed)

        assert uav.mode == "IDLE", (
            f"Drone within arrival threshold ({tiny_offset:.6f} deg) should be IDLE, got {uav.mode}"
        )

    def test_rtb_does_not_transition_to_idle_far_from_home(self):
        """Drone far from home must NOT transition to IDLE."""
        home_x, home_y = 25.0, 45.5
        uav = _make_uav(x=25.5, y=46.0, home_x=home_x, home_y=home_y)
        speed = 0.05
        dt = 1.0

        uav.update(dt, speed)

        assert uav.mode == "RTB", "Drone far from home should remain RTB"

    def test_rtb_eventually_reaches_home_and_goes_idle(self):
        """Drone pointing toward home should reach it and become IDLE."""
        home_x, home_y = 25.0, 45.5
        # 0.05 deg away (~5.5km), already pointing toward home via _make_uav
        uav = _make_uav(x=25.05, y=45.5, home_x=home_x, home_y=home_y)
        speed = 0.05
        dt = 1.0

        max_ticks = 500
        for _ in range(max_ticks):
            uav.update(dt, speed)
            if uav.mode == "IDLE":
                break

        assert uav.mode == "IDLE", (
            f"Drone did not reach home after {max_ticks} ticks. "
            f"Final position: ({uav.x:.4f}, {uav.y:.4f}), home: ({home_x}, {home_y})"
        )


# ---------------------------------------------------------------------------
# Test 4 — home_position from spawn / theater config
# ---------------------------------------------------------------------------

class TestRtbHomeFromSpawnPosition:
    def test_uav_has_home_position_attribute(self):
        """UAV should have home_position attribute after construction."""
        uav = UAV(id=1, x=25.0, y=45.5, zone_id=(0, 0))
        assert hasattr(uav, "home_position"), "UAV should have home_position attribute"

    def test_uav_home_position_is_tuple(self):
        """home_position should be a (lon, lat) tuple."""
        uav = UAV(id=1, x=25.0, y=45.5, zone_id=(0, 0))
        assert isinstance(uav.home_position, tuple), (
            f"home_position should be a tuple, got {type(uav.home_position)}"
        )
        assert len(uav.home_position) == 2, (
            f"home_position should have 2 elements, got {len(uav.home_position)}"
        )

    def test_uav_home_position_defaults_to_spawn_location(self):
        """When no theater config is used, home_position defaults to spawn (x, y)."""
        spawn_x, spawn_y = 25.123, 45.678
        uav = UAV(id=1, x=spawn_x, y=spawn_y, zone_id=(0, 0))
        assert uav.home_position == (spawn_x, spawn_y), (
            f"home_position {uav.home_position} should default to spawn ({spawn_x}, {spawn_y})"
        )

    def test_simulation_model_sets_home_from_theater_base(self):
        """SimulationModel should set home_position from theater base_lon/base_lat."""
        from sim_engine import SimulationModel
        sim = SimulationModel(theater_name="romania")
        for uav in sim.uavs:
            assert hasattr(uav, "home_position"), f"UAV {uav.id} missing home_position"
            home_x, home_y = uav.home_position
            # Romania theater base is (25.0, 45.5)
            assert home_x == pytest.approx(25.0, abs=0.01), (
                f"UAV {uav.id} home_x {home_x} should match theater base_lon 25.0"
            )
            assert home_y == pytest.approx(45.5, abs=0.01), (
                f"UAV {uav.id} home_y {home_y} should match theater base_lat 45.5"
            )
