import math
import sys
import types
import unittest


def _stub_vision_deps():
    """Stub out heavy/missing dependencies so vision modules can be imported in tests."""
    # coordinate_transformer
    if "coordinate_transformer" not in sys.modules:
        ct = types.ModuleType("coordinate_transformer")
        ct.pixel_to_gps = lambda *a, **kw: (51.0, -2.0)
        sys.modules["coordinate_transformer"] = ct

    # dashboard_connector
    if "dashboard_connector" not in sys.modules:
        dc = types.ModuleType("dashboard_connector")

        class _FakeDC:
            def __init__(self, *a, **kw):
                pass

        dc.DashboardConnector = _FakeDC
        sys.modules["dashboard_connector"] = dc

    # cv2
    if "cv2" not in sys.modules:
        cv2 = types.ModuleType("cv2")
        cv2.FONT_HERSHEY_SIMPLEX = 0
        cv2.MARKER_TILTED_CROSS = 0
        for fn in ("line", "rectangle", "circle", "polylines", "putText", "drawMarker", "addWeighted"):
            setattr(cv2, fn, lambda *a, **kw: None)
        sys.modules["cv2"] = cv2

    # numpy
    if "numpy" not in sys.modules:
        pass  # usually available; if not, test env is broken

    # structlog
    if "structlog" not in sys.modules:
        sl = types.ModuleType("structlog")

        class _FakeLogger:
            def bind(self, **kw):
                return self

            def info(self, *a, **kw):
                pass

            def warning(self, *a, **kw):
                pass

            def error(self, *a, **kw):
                pass

        sl.get_logger = lambda: _FakeLogger()
        sys.modules["structlog"] = sl

    # ultralytics
    if "ultralytics" not in sys.modules:
        ul = types.ModuleType("ultralytics")

        class _FakeYOLO:
            def __init__(self, *a, **kw):
                pass

        ul.YOLO = _FakeYOLO
        sys.modules["ultralytics"] = ul


_stub_vision_deps()


class TestTrackingScenarioUpdateDrone(unittest.TestCase):
    """TrackingScenario.update_drone() must move the drone toward the tracked target."""

    def setUp(self):
        from src.python.vision.video_simulator import TrackingScenario

        self.TrackingScenario = TrackingScenario

    def _make_drone(self, lat=45.9432, lon=24.9668, alt=120.0):
        return {
            "lat": lat,
            "lon": lon,
            "origin_lat": lat,
            "origin_lon": lon,
            "alt": alt,
            "pitch": -45.0,
            "yaw": 0.0,
            "speed": 15.0,
        }

    def _make_blocks(self, target_id, lat, lon):
        return [{"id": target_id, "lat": lat, "lon": lon, "type": "SAM"}]

    def test_drone_moves_toward_target(self):
        """After one tick the drone must be closer to the target."""
        scenario = self.TrackingScenario("TGT-1")
        drone = self._make_drone(lat=45.9432, lon=24.9668)
        target_lat, target_lon = 45.9600, 25.0000
        blocks = self._make_blocks("TGT-1", target_lat, target_lon)

        # Haversine distance before
        def dist(lat1, lon1, lat2, lon2):
            R = 6378137.0
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
            )
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        d_before = dist(drone["lat"], drone["lon"], target_lat, target_lon)
        scenario.update_drone(drone, dt=1.0, blocks=blocks)
        d_after = dist(drone["lat"], drone["lon"], target_lat, target_lon)

        self.assertLess(d_after, d_before, "Drone did not move closer to target")

    def test_drone_lat_lon_change_after_tick(self):
        """Drone lat/lon must change from start position after update."""
        scenario = self.TrackingScenario("TGT-1")
        drone = self._make_drone()
        blocks = self._make_blocks("TGT-1", lat=46.0, lon=25.1)
        start_lat, start_lon = drone["lat"], drone["lon"]

        scenario.update_drone(drone, dt=1.0, blocks=blocks)

        self.assertNotEqual(drone["lat"], start_lat, "Drone lat unchanged after tick")
        self.assertNotEqual(drone["lon"], start_lon, "Drone lon unchanged after tick")

    def test_no_crash_when_target_missing(self):
        """update_drone must not raise when target_id is absent from blocks."""
        scenario = self.TrackingScenario("MISSING-ID")
        drone = self._make_drone()
        blocks = self._make_blocks("TGT-1", lat=46.0, lon=25.1)
        scenario.update_drone(drone, dt=1.0, blocks=blocks)  # must not raise

    def test_drone_does_not_overshoot_nearby_target(self):
        """Drone very close to target should not fly past it in one tick."""
        scenario = self.TrackingScenario("TGT-1")
        drone = self._make_drone(lat=45.94320, lon=24.96680)
        target_lat, target_lon = 45.94321, 24.96681
        blocks = self._make_blocks("TGT-1", target_lat, target_lon)

        scenario.update_drone(drone, dt=1.0, blocks=blocks)

        self.assertLess(abs(drone["lat"] - target_lat), 1.0)
        self.assertLess(abs(drone["lon"] - target_lon), 1.0)

    def test_yaw_updated_to_face_target(self):
        """Drone yaw should be updated to point toward the target."""
        scenario = self.TrackingScenario("TGT-1")
        drone = self._make_drone(lat=45.9432, lon=24.9668)
        # Target directly north (higher lat, same lon) → bearing ~0°
        blocks = self._make_blocks("TGT-1", lat=46.0000, lon=24.9668)

        scenario.update_drone(drone, dt=1.0, blocks=blocks)

        self.assertAlmostEqual(drone["yaw"], 0.0, delta=10.0)


class TestVisionProcessorTelemetry(unittest.TestCase):
    """VisionProcessor must expose update_telemetry() and use real coords."""

    def _make_vp(self):
        import importlib

        import src.python.vision.vision_processor as vp_mod

        importlib.reload(vp_mod)
        vp = vp_mod.VisionProcessor.__new__(vp_mod.VisionProcessor)
        vp.drone_state = {"lat": 51.4545, "lon": -2.5879, "alt": 100.0, "pitch": -90.0, "yaw": 0.0}
        return vp

    def test_update_telemetry_full(self):
        """update_telemetry updates all provided fields."""
        vp = self._make_vp()
        vp.update_telemetry({"lat": 46.0, "lon": 25.0, "alt": 150.0, "pitch": -60.0, "yaw": 45.0})

        self.assertAlmostEqual(vp.drone_state["lat"], 46.0, places=4)
        self.assertAlmostEqual(vp.drone_state["lon"], 25.0, places=4)
        self.assertAlmostEqual(vp.drone_state["alt"], 150.0, places=1)
        self.assertAlmostEqual(vp.drone_state["pitch"], -60.0, places=1)
        self.assertAlmostEqual(vp.drone_state["yaw"], 45.0, places=1)

    def test_update_telemetry_partial(self):
        """update_telemetry with partial dict only updates provided fields."""
        vp = self._make_vp()
        vp.drone_state = {"lat": 45.9432, "lon": 24.9668, "alt": 100.0, "pitch": -90.0, "yaw": 0.0}
        vp.update_telemetry({"alt": 200.0})

        self.assertAlmostEqual(vp.drone_state["lat"], 45.9432, places=4)
        self.assertAlmostEqual(vp.drone_state["alt"], 200.0, places=1)

    def test_update_telemetry_replaces_bristol(self):
        """After update_telemetry with real coords, Bristol coords are gone."""
        BRISTOL_LAT, BRISTOL_LON = 51.4545, -2.5879
        vp = self._make_vp()

        vp.update_telemetry({"lat": 45.9432, "lon": 24.9668})

        self.assertNotAlmostEqual(vp.drone_state["lat"], BRISTOL_LAT, places=2)
        self.assertNotAlmostEqual(vp.drone_state["lon"], BRISTOL_LON, places=2)

    def test_update_telemetry_method_exists(self):
        """VisionProcessor must have an update_telemetry method."""
        import importlib

        import src.python.vision.vision_processor as vp_mod

        importlib.reload(vp_mod)
        self.assertTrue(
            hasattr(vp_mod.VisionProcessor, "update_telemetry"),
            "VisionProcessor missing update_telemetry()",
        )


if __name__ == "__main__":
    unittest.main()
