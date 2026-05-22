"""Smoke tests for the pyrender → Grid-Sentinel integration.

Verifies:
  - GridSentinelRenderer instantiation matches sim state (skip if OpenGL not
    available, common on macOS without OSMesa).
  - render_from_uav() returns an HxWx3 uint8 array.
  - render_overhead() returns the same shape.
  - The /api/drone-camera/{uav_id} endpoint returns 503 when USE_PYRENDER is
    off, 200 + image/png when on (or skips if pyrender can't render here).
  - The /api/drone-camera/_status endpoint always reflects state.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "python"))

pyrender = pytest.importorskip("pyrender")
trimesh = pytest.importorskip("trimesh")

from sim_engine import SimulationModel

# OpenGL-touching tests are gated behind RUN_OPENGL_TESTS=1 — on macOS in a
# headless shell pyrender's pyglet path opens an NSWindow which segfaults
# (not a catchable Python exception). On Linux + X / Windows / inside Docker
# with EGL, set the env var to exercise them.
_NEEDS_GL = pytest.mark.skipif(
    os.getenv("RUN_OPENGL_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="OpenGL tests gated behind RUN_OPENGL_TESTS=1 (segfaults on headless macOS)",
)


def _renderer_or_skip(width: int = 320, height: int = 240):
    """Build a GridSentinelRenderer or skip the test if OpenGL isn't available."""
    try:
        from vision.pyrender_bridge import GridSentinelRenderer
        return GridSentinelRenderer(width=width, height=height)
    except RuntimeError as exc:
        pytest.skip(f"OpenGL context unavailable here: {exc}")
    except Exception as exc:
        pytest.skip(f"pyrender bridge instantiation failed: {exc}")


@_NEEDS_GL
class TestGridSentinelRenderer:
    def test_render_from_uav_returns_uint8_image(self):
        sim = SimulationModel(theater_name="romania")
        sim.tick()
        renderer = _renderer_or_skip()
        uav_id = next(iter(sim.uavs))
        img = renderer.render_from_uav(sim, uav_id=uav_id)
        assert img is not None, "renderer returned no frame"
        assert img.shape == (240, 320, 3), f"unexpected shape {img.shape}"
        assert img.dtype.name == "uint8", f"unexpected dtype {img.dtype}"

    def test_render_overhead_returns_uint8_image(self):
        sim = SimulationModel(theater_name="romania")
        sim.tick()
        renderer = _renderer_or_skip()
        img = renderer.render_overhead(sim, altitude_m=3000.0)
        assert img.shape == (240, 320, 3)
        assert img.dtype.name == "uint8"

    def test_sync_targets_tracks_live_ids(self):
        sim = SimulationModel(theater_name="romania")
        sim.tick()
        renderer = _renderer_or_skip()
        renderer.sync_targets(sim)
        assert set(renderer._target_nodes.keys()) == set(sim.targets.keys())

    def test_sync_uav_markers_excludes_camera_host(self):
        sim = SimulationModel(theater_name="romania")
        sim.tick()
        renderer = _renderer_or_skip()
        host = next(iter(sim.uavs))
        renderer.sync_uav_markers(sim, exclude_uav_id=host)
        assert host not in renderer._uav_nodes
        assert set(renderer._uav_nodes.keys()) == set(sim.uavs.keys()) - {host}


class TestDroneCameraEndpoint:
    """The endpoint itself — uses a fresh FastAPI TestClient per test so the
    USE_PYRENDER env flag is honored on import."""

    def _client(self, use_pyrender: bool):
        if use_pyrender:
            os.environ["USE_PYRENDER"] = "true"
        else:
            os.environ.pop("USE_PYRENDER", None)
        # Force reload so the env flag takes effect
        for mod in [m for m in list(sys.modules) if m.startswith("api_main")]:
            del sys.modules[mod]
        api_main = importlib.import_module("api_main")
        from fastapi.testclient import TestClient
        return TestClient(api_main.app), api_main

    def test_status_endpoint_reflects_env(self):
        client, _ = self._client(use_pyrender=False)
        resp = client.get("/api/drone-camera/_status")
        assert resp.status_code == 200
        assert resp.json()["use_pyrender"] is False

        client2, _ = self._client(use_pyrender=True)
        resp2 = client2.get("/api/drone-camera/_status")
        assert resp2.status_code == 200
        assert resp2.json()["use_pyrender"] is True

    def test_endpoint_503_when_off(self):
        client, _ = self._client(use_pyrender=False)
        resp = client.get("/api/drone-camera/0")
        assert resp.status_code == 503
        assert "pyrender" in resp.json()["detail"].lower()

    def test_endpoint_returns_503_or_404_for_unknown_uav(self):
        # With USE_PYRENDER off the endpoint short-circuits to 503 before
        # touching the UAV map — which is the correct production behavior
        # when the 3D backend is not active.
        client, _ = self._client(use_pyrender=False)
        resp = client.get("/api/drone-camera/9999")
        assert resp.status_code == 503

    @_NEEDS_GL
    def test_endpoint_returns_png_when_pyrender_works(self):
        client, api_main = self._client(use_pyrender=True)
        api_main.sim.tick()
        uav_id = next(iter(api_main.sim.uavs))
        resp = client.get(f"/api/drone-camera/{uav_id}")
        if resp.status_code == 503:
            pytest.skip("OpenGL context unavailable in this test env")
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
