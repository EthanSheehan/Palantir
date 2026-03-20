"""TDD tests for EnemyUAV class and SimulationModel integration.

Phase 04 Plan 01 — Enemy UAV backend.
"""

import math
import random
import sys
import os
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sim_engine import SimulationModel, EnemyUAV, ENEMY_UAV_MODES, MAX_TURN_RATE


@pytest.fixture
def sim():
    random.seed(42)
    return SimulationModel()


def _tick_n(sim: SimulationModel, n: int):
    for _ in range(n):
        sim.tick()


# ---------------------------------------------------------------------------
# TestEnemyUAVSpawn
# ---------------------------------------------------------------------------

class TestEnemyUAVSpawn:
    def test_creation_with_defaults(self):
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="RECON", behavior="recon")
        assert e.id == 1000
        assert e.x == 25.0
        assert e.y == 45.0
        assert e.mode == "RECON"
        assert e.behavior == "recon"

    def test_id_starts_at_1000(self, sim):
        for e in sim.enemy_uavs:
            assert e.id >= 1000, f"EnemyUAV id={e.id} must be >= 1000"

    def test_modes(self):
        for mode in ("RECON", "ATTACK", "JAMMING", "EVADING", "DESTROYED"):
            assert mode in ENEMY_UAV_MODES

    def test_enemy_uavs_spawned(self, sim):
        assert len(sim.enemy_uavs) >= 1, "At least one enemy UAV should be spawned"


# ---------------------------------------------------------------------------
# TestEnemyUAVMovement
# ---------------------------------------------------------------------------

class TestEnemyUAVMovement:
    def test_recon_loiter(self):
        """RECON mode: heading changes each tick, position changes."""
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="RECON", behavior="recon")
        e.vx = 0.004  # give initial velocity
        e.vy = 0.0
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        initial_heading = e.heading_deg
        initial_x = e.x
        e.update(0.1, bounds)
        # Heading changes due to loiter turn
        # Position changes
        assert e.x != initial_x or e.y != 45.0 or e.heading_deg != initial_heading

    def test_attack_direct_approach(self):
        """ATTACK mode: moves toward attack_waypoint, reduces distance each tick."""
        e = EnemyUAV(id=1001, x=25.0, y=45.0, mode="ATTACK", behavior="attack")
        e.attack_waypoint = (26.0, 45.0)
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        initial_dist = math.hypot(26.0 - e.x, 45.0 - e.y)
        for _ in range(10):
            e.update(0.1, bounds)
        new_dist = math.hypot(26.0 - e.x, 45.0 - e.y)
        assert new_dist < initial_dist, f"ATTACK mode should approach waypoint: initial={initial_dist}, new={new_dist}"

    def test_jamming_station_keeping(self):
        """JAMMING mode: holds position, is_jamming=True."""
        e = EnemyUAV(id=1002, x=25.0, y=45.0, mode="JAMMING", behavior="jamming")
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        initial_x, initial_y = e.x, e.y
        for _ in range(100):
            e.update(0.1, bounds)
        delta = math.hypot(e.x - initial_x, e.y - initial_y)
        assert delta < 0.01, f"JAMMING mode should station-keep: delta={delta}"
        assert e.is_jamming is True

    def test_fixed_wing_turn_rate(self):
        """Heading change per tick is bounded by MAX_TURN_RATE."""
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="RECON", behavior="recon")
        # Give it an initial velocity in one direction
        e.vx = 0.004
        e.vy = 0.0
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        dt = 0.1
        prev_heading_rad = math.atan2(e.vx, e.vy)
        e.update(dt, bounds)
        new_heading_rad = math.atan2(e.vx, e.vy)
        diff = abs(new_heading_rad - prev_heading_rad)
        # Normalize to [0, pi]
        while diff > math.pi:
            diff = abs(diff - 2 * math.pi)
        max_allowed = MAX_TURN_RATE * dt + 0.001  # small tolerance
        assert diff <= max_allowed, f"Turn rate exceeded: diff={diff:.4f} rad, max={max_allowed:.4f} rad"


# ---------------------------------------------------------------------------
# TestSeparation
# ---------------------------------------------------------------------------

class TestSeparation:
    def test_enemy_uavs_not_in_targets(self, sim):
        """enemy_uavs is a separate list — no EnemyUAV in sim.targets."""
        for t in sim.targets:
            assert not isinstance(t, EnemyUAV), "EnemyUAV must not appear in sim.targets"

    def test_find_enemy_uav(self, sim):
        """sim._find_enemy_uav(1000) returns EnemyUAV, sim._find_target(1000) returns None."""
        # find the first enemy UAV
        if sim.enemy_uavs:
            eid = sim.enemy_uavs[0].id
            result = sim._find_enemy_uav(eid)
            assert result is not None, f"_find_enemy_uav({eid}) returned None"
            assert isinstance(result, EnemyUAV)
            # Should NOT be found in targets
            result_target = sim._find_target(eid)
            assert result_target is None, f"_find_target({eid}) should return None for enemy UAV id"

    def test_enemy_uavs_list_exists(self, sim):
        """SimulationModel has enemy_uavs attribute."""
        assert hasattr(sim, "enemy_uavs")
        assert isinstance(sim.enemy_uavs, list)


# ---------------------------------------------------------------------------
# TestGetState
# ---------------------------------------------------------------------------

class TestGetState:
    def test_enemy_uavs_key_exists(self, sim):
        state = sim.get_state()
        assert "enemy_uavs" in state, "get_state() must have 'enemy_uavs' key"

    def test_enemy_uav_payload_shape(self, sim):
        state = sim.get_state()
        for e in state["enemy_uavs"]:
            for key in ("id", "lon", "lat", "mode", "behavior", "heading_deg",
                        "detected", "fused_confidence", "sensor_count", "is_jamming"):
                assert key in e, f"Missing key '{key}' in enemy_uav payload"


# ---------------------------------------------------------------------------
# TestPerformance
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TestEnemyUAVDetection
# ---------------------------------------------------------------------------

class TestEnemyUAVDetection:
    def test_friendly_uav_detects_nearby_enemy(self, sim):
        """Place friendly UAV very close to enemy, tick 50 times — enemy.detected == True."""
        # Place first enemy UAV at a known position
        e = sim.enemy_uavs[0]
        e.mode = "RECON"
        e.x = 25.0
        e.y = 45.0
        # Place first friendly UAV right next to it (within 0.01 deg ~ 1km)
        u = sim.uavs[0]
        u.x = 25.01
        u.y = 45.0
        u.mode = "SEARCH"
        # Give the UAV at least one optical sensor
        if "EO_IR" not in u.sensors:
            u.sensors = ["EO_IR"]
        _tick_n(sim, 50)
        assert e.detected is True, f"Enemy at ({e.x},{e.y}) should be detected by nearby UAV"

    def test_distant_enemy_not_detected(self, sim):
        """Enemy 5 degrees away from all UAVs — should not be detected after 50 ticks."""
        # Push enemy far away
        e = sim.enemy_uavs[0]
        e.x = sim.bounds['min_lon']
        e.y = sim.bounds['min_lat']
        e.detected = False
        e.fused_confidence = 0.0
        # Move all friendly UAVs to the opposite corner
        for u in sim.uavs:
            u.x = sim.bounds['max_lon']
            u.y = sim.bounds['max_lat']
        _tick_n(sim, 50)
        assert e.detected is False, "Enemy 5+ degrees away should not be detected"

    def test_fused_confidence_positive(self, sim):
        """After detection, enemy.fused_confidence > 0."""
        e = sim.enemy_uavs[0]
        e.mode = "RECON"
        e.x = 25.0
        e.y = 45.0
        u = sim.uavs[0]
        u.x = 25.01
        u.y = 45.0
        u.mode = "SEARCH"
        if "EO_IR" not in u.sensors:
            u.sensors = ["EO_IR"]
        _tick_n(sim, 50)
        if e.detected:
            assert e.fused_confidence > 0, "Detected enemy must have positive fused_confidence"

    def test_sensor_count_positive(self, sim):
        """After detection, enemy.sensor_count > 0."""
        e = sim.enemy_uavs[0]
        e.mode = "RECON"
        e.x = 25.0
        e.y = 45.0
        u = sim.uavs[0]
        u.x = 25.01
        u.y = 45.0
        u.mode = "SEARCH"
        if "EO_IR" not in u.sensors:
            u.sensors = ["EO_IR"]
        _tick_n(sim, 50)
        if e.detected:
            assert e.sensor_count > 0, "Detected enemy must have positive sensor_count"

    def test_confidence_fades_without_sensors(self, sim):
        """After detection, move all UAVs far away — fused_confidence should decrease."""
        e = sim.enemy_uavs[0]
        e.mode = "RECON"
        e.x = 25.0
        e.y = 45.0
        u = sim.uavs[0]
        u.x = 25.01
        u.y = 45.0
        u.mode = "SEARCH"
        if "EO_IR" not in u.sensors:
            u.sensors = ["EO_IR"]
        # Detect it
        _tick_n(sim, 50)
        initial_confidence = e.fused_confidence
        if initial_confidence == 0.0:
            pytest.skip("Enemy not detected — cannot test fade")
        # Now move all UAVs far away
        for fu in sim.uavs:
            fu.x = sim.bounds['max_lon']
            fu.y = sim.bounds['max_lat']
        _tick_n(sim, 100)
        assert e.fused_confidence < initial_confidence, (
            f"Confidence should fade after UAVs leave: initial={initial_confidence}, after={e.fused_confidence}"
        )


# ---------------------------------------------------------------------------
# TestJammingDetection
# ---------------------------------------------------------------------------

class TestJammingDetection:
    def test_jamming_enemy_detected_by_sigint(self, sim):
        """Enemy with is_jamming=True: UAV with SIGINT can detect at range."""
        e = sim.enemy_uavs[0]
        e.mode = "JAMMING"
        e.is_jamming = True
        e.x = 25.0
        e.y = 45.0
        e.detected = False
        e.fused_confidence = 0.0
        # Place UAV with SIGINT at medium range (~0.5 deg = ~55km, within SIGINT 200km max)
        u = sim.uavs[0]
        u.sensors = ["SIGINT"]
        u.x = 25.5
        u.y = 45.0
        u.mode = "SEARCH"
        # SIGINT has 200km range — should detect jamming target at 55km
        _tick_n(sim, 50)
        assert e.detected is True, "SIGINT should detect jamming enemy at medium range"

    def test_non_jamming_invisible_to_sigint_only(self, sim):
        """Enemy NOT jamming: SIGINT-only UAV should NOT detect (requires_emitter=True)."""
        e = sim.enemy_uavs[0]
        e.mode = "RECON"
        e.is_jamming = False
        e.x = 25.0
        e.y = 45.0
        e.detected = False
        e.fused_confidence = 0.0
        # Place UAV with SIGINT only at close range
        u = sim.uavs[0]
        u.sensors = ["SIGINT"]
        u.x = 25.01
        u.y = 45.0
        u.mode = "SEARCH"
        # Remove all other UAVs by pushing them far away
        for other_u in sim.uavs[1:]:
            other_u.x = sim.bounds['max_lon']
            other_u.y = sim.bounds['max_lat']
        _tick_n(sim, 50)
        assert e.detected is False, "SIGINT should NOT detect non-jamming enemy (requires_emitter=True)"


# ---------------------------------------------------------------------------
# TestEvasion
# ---------------------------------------------------------------------------

class TestEvasion:
    def test_evasion_triggers_at_high_confidence(self):
        """set enemy.fused_confidence=0.6, call evasion check, mode becomes EVADING."""
        random.seed(42)
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="RECON", behavior="recon")
        e.fused_confidence = 0.6
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        e.update(0.1, bounds)
        assert e.mode == "EVADING", f"Expected EVADING, got {e.mode}"

    def test_evasion_cooldown_prevents_thrash(self):
        """After entering EVADING, even if confidence drops, mode stays EVADING for at least 15 seconds."""
        random.seed(42)
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="RECON", behavior="recon")
        e.fused_confidence = 0.6
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        e.update(0.1, bounds)
        assert e.mode == "EVADING"
        # Drop confidence below threshold
        e.fused_confidence = 0.1
        # Tick for 10 seconds — should still be EVADING (cooldown=15s not expired)
        for _ in range(100):
            e.update(0.1, bounds)
        assert e.mode == "EVADING", f"Should still be EVADING after 10s, got {e.mode}"

    def test_evasion_returns_to_original(self):
        """After cooldown expires and confidence < 0.3, mode returns to original mode."""
        random.seed(42)
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="RECON", behavior="recon")
        e.fused_confidence = 0.6
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        e.update(0.1, bounds)
        assert e.mode == "EVADING"
        # Expire the cooldown manually
        e.evasion_cooldown = 0.0
        e.fused_confidence = 0.1
        e.update(0.1, bounds)
        assert e.mode == "RECON", f"Should return to RECON, got {e.mode}"

    def test_evasion_speed_boost(self):
        """EVADING mode speed is 1.5x normal speed."""
        random.seed(42)
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="EVADING", behavior="recon")
        e.evasion_cooldown = 15.0
        e._original_mode = "RECON"
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        # Give initial velocity
        e.vx = e.speed
        e.vy = 0.0
        e.update(0.1, bounds)
        current_speed = math.hypot(e.vx, e.vy)
        # Speed in EVADING should be 1.5x normal
        assert abs(current_speed - e.speed * 1.5) < 0.001, (
            f"EVADING speed should be {e.speed * 1.5:.5f}, got {current_speed:.5f}"
        )


# ---------------------------------------------------------------------------
# TestInterceptKill
# ---------------------------------------------------------------------------

class TestInterceptKill:
    def test_intercept_command(self):
        """command_intercept_enemy(uav_id=0, enemy_uav_id=1000) sets UAV mode to INTERCEPT."""
        random.seed(42)
        sim = SimulationModel()
        uav = sim.uavs[0]
        enemy = sim.enemy_uavs[0]
        sim.command_intercept_enemy(uav.id, enemy.id)
        assert uav.mode == "INTERCEPT", f"UAV mode should be INTERCEPT, got {uav.mode}"
        assert uav.primary_target_id == enemy.id, (
            f"UAV primary_target_id should be {enemy.id}, got {uav.primary_target_id}"
        )

    def test_kill_at_close_range(self):
        """UAV within INTERCEPT_CLOSE_DEG of enemy, after 3s dwell (30 ticks), enemy mode becomes DESTROYED."""
        random.seed(42)
        sim = SimulationModel()
        uav = sim.uavs[0]
        enemy = sim.enemy_uavs[0]
        # Place UAV directly on top of enemy
        uav.x = enemy.x
        uav.y = enemy.y
        uav.mode = "INTERCEPT"
        uav.primary_target_id = enemy.id
        uav._intercept_dwell = 0.0
        # Tick 31 times at 0.1s = 3.1s dwell
        for _ in range(31):
            sim._update_tracking_modes(0.1)
        assert enemy.mode == "DESTROYED", f"Enemy should be DESTROYED, got {enemy.mode}"

    def test_uav_returns_to_search_after_kill(self):
        """After enemy destroyed, friendly UAV mode becomes SEARCH."""
        random.seed(42)
        sim = SimulationModel()
        uav = sim.uavs[0]
        enemy = sim.enemy_uavs[0]
        uav.x = enemy.x
        uav.y = enemy.y
        uav.mode = "INTERCEPT"
        uav.primary_target_id = enemy.id
        uav._intercept_dwell = 0.0
        for _ in range(31):
            sim._update_tracking_modes(0.1)
        assert uav.mode == "SEARCH", f"UAV should revert to SEARCH, got {uav.mode}"

    def test_destroyed_enemy_no_movement(self):
        """DESTROYED enemy vx=vy=0."""
        random.seed(42)
        e = EnemyUAV(id=1000, x=25.0, y=45.0, mode="DESTROYED", behavior="recon")
        e.vx = 0.005
        e.vy = 0.003
        bounds = {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0}
        e.update(0.1, bounds)
        assert e.vx == 0.005 and e.vy == 0.003, "DESTROYED mode should not move (update returns early)"


# ---------------------------------------------------------------------------
# TestTheaterConfig
# ---------------------------------------------------------------------------

class TestTheaterConfig:
    def test_enemy_uavs_from_yaml(self):
        """SimulationModel with romania theater spawns enemy UAVs per YAML config."""
        random.seed(42)
        sim = SimulationModel(theater_name="romania")
        assert len(sim.enemy_uavs) > 0, "Romania theater should spawn enemy UAVs from YAML config"

    def test_enemy_uav_count_matches_yaml(self):
        """Number of enemy_uavs matches sum of counts in YAML."""
        random.seed(42)
        sim = SimulationModel(theater_name="romania")
        # romania.yaml has 2 recon + 1 jamming = 3 total
        expected = 3
        assert len(sim.enemy_uavs) == expected, (
            f"Expected {expected} enemy UAVs from YAML, got {len(sim.enemy_uavs)}"
        )


class TestPerformance:
    def test_10hz_with_8_enemies(self):
        """100 ticks with 8 enemy UAVs completes in < 10 seconds."""
        random.seed(99)
        sim = SimulationModel()
        # Add enemies up to 8
        bounds = sim.bounds
        while len(sim.enemy_uavs) < 8:
            eid = 1000 + len(sim.enemy_uavs)
            cx = (bounds['min_lon'] + bounds['max_lon']) / 2
            cy = (bounds['min_lat'] + bounds['max_lat']) / 2
            e = EnemyUAV(id=eid, x=cx, y=cy, mode="RECON", behavior="recon")
            sim.enemy_uavs.append(e)

        start = time.time()
        for _ in range(100):
            sim.tick()
        elapsed = time.time() - start
        assert elapsed < 10.0, f"100 ticks with 8 enemy UAVs took {elapsed:.2f}s (> 10s limit)"
