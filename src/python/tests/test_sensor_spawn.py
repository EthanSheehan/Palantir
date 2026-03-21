"""Tests for multi-sensor UAV spawn, sensor distribution, and theater YAML wiring."""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sim_engine import _SENSOR_DISTRIBUTION, DEG_PER_KM, SimulationModel, _pick_sensors


class TestPickSensors:
    def test_returns_list_of_strings(self):
        result = _pick_sensors()
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_result_is_nonempty(self):
        result = _pick_sensors()
        assert len(result) >= 1

    def test_result_contains_known_sensors(self):
        known = {"EO_IR", "SAR", "SIGINT"}
        for _ in range(50):
            result = _pick_sensors()
            assert all(s in known for s in result)

    def test_distribution_probabilities(self):
        random.seed(0)
        n = 1000
        counts = {tuple(s): 0 for s, _ in _SENSOR_DISTRIBUTION}
        for _ in range(n):
            result = tuple(_pick_sensors())
            if result in counts:
                counts[result] += 1

        # EO_IR only: expect ~50% ± 5%
        assert 0.44 <= counts[("EO_IR",)] / n <= 0.56, (
            f"EO_IR-only rate {counts[('EO_IR',)] / n:.3f} out of expected 0.44-0.56"
        )
        # SAR only: expect ~20% ± 4%
        assert 0.15 <= counts[("SAR",)] / n <= 0.26, (
            f"SAR-only rate {counts[('SAR',)] / n:.3f} out of expected 0.15-0.26"
        )
        # SIGINT only: expect ~10% ± 4%
        assert 0.06 <= counts[("SIGINT",)] / n <= 0.15, (
            f"SIGINT-only rate {counts[('SIGINT',)] / n:.3f} out of expected 0.06-0.15"
        )
        # Dual EO_IR+SAR: expect ~10% ± 4%
        assert 0.06 <= counts[("EO_IR", "SAR")] / n <= 0.15, (
            f"EO_IR+SAR rate {counts[('EO_IR', 'SAR')] / n:.3f} out of expected 0.06-0.15"
        )
        # Dual EO_IR+SIGINT: expect ~10% ± 4%
        assert 0.06 <= counts[("EO_IR", "SIGINT")] / n <= 0.15, (
            f"EO_IR+SIGINT rate {counts[('EO_IR', 'SIGINT')] / n:.3f} out of expected 0.06-0.15"
        )


class TestUAVSensorsField:
    def test_all_uavs_have_sensors_list(self):
        random.seed(42)
        sim = SimulationModel()
        for u in sim.uavs.values():
            assert hasattr(u, "sensors"), f"UAV {u.id} missing sensors attribute"
            assert isinstance(u.sensors, list)
            assert len(u.sensors) >= 1

    def test_sensors_appear_in_get_state(self):
        random.seed(42)
        sim = SimulationModel()
        state = sim.get_state()
        for uav_state in state["uavs"]:
            assert "sensors" in uav_state, f"UAV {uav_state['id']} missing sensors in state"
            assert isinstance(uav_state["sensors"], list)
            assert len(uav_state["sensors"]) >= 1

    def test_sensors_are_valid_strings(self):
        random.seed(42)
        sim = SimulationModel()
        known = {"EO_IR", "SAR", "SIGINT"}
        for u in sim.uavs.values():
            for s in u.sensors:
                assert s in known, f"Unknown sensor '{s}' on UAV {u.id}"


class TestTheaterYAMLWiring:
    def test_speed_kmh_wired_into_target_speed(self):
        random.seed(42)
        sim = SimulationModel("romania")
        # TEL has speed_kmh: 40 in romania.yaml
        # 40 km/h * DEG_PER_KM / 3600 should match
        expected_speed = 40 * DEG_PER_KM / 3600.0
        tel_targets = [t for t in sim.targets.values() if t.type == "TEL"]
        assert len(tel_targets) > 0, "No TEL targets spawned"
        for t in tel_targets:
            assert abs(t.speed - expected_speed) < 1e-10, f"TEL target speed {t.speed} != expected {expected_speed}"

    def test_truck_speed_kmh_wired(self):
        random.seed(42)
        sim = SimulationModel("romania")
        # TRUCK has speed_kmh: 60 in romania.yaml
        expected_speed = 60 * DEG_PER_KM / 3600.0
        truck_targets = [t for t in sim.targets.values() if t.type == "TRUCK"]
        assert len(truck_targets) > 0, "No TRUCK targets spawned"
        for t in truck_targets:
            assert abs(t.speed - expected_speed) < 1e-10, f"TRUCK target speed {t.speed} != expected {expected_speed}"

    def test_threat_range_km_wired(self):
        random.seed(42)
        sim = SimulationModel("romania")
        # SAM has threat_range_km: 30 in romania.yaml
        sam_targets = [t for t in sim.targets.values() if t.type == "SAM"]
        assert len(sam_targets) > 0, "No SAM targets spawned"
        for t in sam_targets:
            assert t.threat_range_km == 30.0, f"SAM threat_range_km {t.threat_range_km} != 30"

    def test_detection_range_km_wired(self):
        random.seed(42)
        sim = SimulationModel("romania")
        # RADAR has detection_range_km: 100 in romania.yaml
        radar_targets = [t for t in sim.targets.values() if t.type == "RADAR"]
        assert len(radar_targets) > 0, "No RADAR targets spawned"
        for t in radar_targets:
            assert t.detection_range_km == 100.0, f"RADAR detection_range_km {t.detection_range_km} != 100"

    def test_threat_range_in_state_broadcast(self):
        random.seed(42)
        sim = SimulationModel("romania")
        state = sim.get_state()
        sam_states = [t for t in state["targets"] if t["type"] == "SAM"]
        assert len(sam_states) > 0
        for t in sam_states:
            assert "threat_range_km" in t
            assert t["threat_range_km"] == 30.0

    def test_detection_range_in_state_broadcast(self):
        random.seed(42)
        sim = SimulationModel("romania")
        state = sim.get_state()
        radar_states = [t for t in state["targets"] if t["type"] == "RADAR"]
        assert len(radar_states) > 0
        for t in radar_states:
            assert "detection_range_km" in t
            assert t["detection_range_km"] == 100.0

    def test_no_speed_for_stationary_units(self):
        random.seed(42)
        sim = SimulationModel("romania")
        # CP has no speed_kmh in romania.yaml — speed should remain at Target default
        cp_targets = [t for t in sim.targets.values() if t.type == "CP"]
        assert len(cp_targets) > 0, "No CP targets spawned"
        # CP targets should NOT be in the speed map
        assert "CP" not in sim._unit_speed_map

    def test_no_threat_range_for_units_without_it(self):
        random.seed(42)
        sim = SimulationModel("romania")
        # TRUCK has no threat_range_km
        truck_targets = [t for t in sim.targets.values() if t.type == "TRUCK"]
        for t in truck_targets:
            assert t.threat_range_km is None
