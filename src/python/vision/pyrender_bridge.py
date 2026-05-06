"""
pyrender_bridge.py
==================
Drop the standalone pyrender pipeline (unreal_to_isaac_target_tracking_2/) into
Grid-Sentinel as a real 3D camera source: take a SimulationModel and render the
current state — drones + targets — from a chosen drone's gimbal.

This wires the C2 system's sim state into the NVIDIA-free renderer that
previously only knew how to drive a hard-coded terminal-dive scenario.

Usage:
    from sim_engine import SimulationModel
    from vision.pyrender_bridge import GridSentinelRenderer

    sim = SimulationModel(theater_name="romania")
    sim.tick()
    renderer = GridSentinelRenderer(width=640, height=480)
    img_array = renderer.render_from_uav(sim, uav_id=next(iter(sim.uavs)))
"""
from __future__ import annotations

import math
import os
import sys
from typing import Dict, Optional, Tuple

import numpy as np

# The pyrender renderer modules live in unreal_to_isaac_target_tracking_2/no_synterra_attempt/.
# We import them as a sibling package by extending sys.path lazily.
_PIPELINE_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "unreal_to_isaac_target_tracking_2",
        "no_synterra_attempt",
    )
)
if _PIPELINE_DIR not in sys.path:
    sys.path.insert(0, _PIPELINE_DIR)

import pyrender  # noqa: E402

from renderer import DroneCamera, OffscreenRenderer, SceneBuilder  # noqa: E402

EARTH_RADIUS_M = 6_378_137.0


def _lonlat_to_local_cm(
    lon: float,
    lat: float,
    origin_lon: float,
    origin_lat: float,
) -> Tuple[float, float]:
    """Flat-earth approximation: GPS → local (x_east, z_north) in cm relative to origin."""
    cos_lat = math.cos(math.radians(origin_lat))
    dx_m = math.radians(lon - origin_lon) * EARTH_RADIUS_M * cos_lat
    dz_m = math.radians(lat - origin_lat) * EARTH_RADIUS_M
    # Renderer convention: X east, Z north (flip sign so north is -Z if needed)
    return (dx_m * 100.0, dz_m * 100.0)


class GridSentinelRenderer:
    """
    Renders Grid-Sentinel SimulationModel state through the pyrender pipeline.

    Loads the same terrain mesh `run_pyrender.py` uses (Swiss-Alps DEM by default)
    as a visual backdrop. Drones and targets from the live sim are placed on top
    via flat-earth projection, scaled so they read at ~5 km radius around the POI.
    The camera attaches to a UAV's position + heading.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        terrain_dir: Optional[str] = None,
        scene_radius_m: float = 5_000.0,
    ):
        self.width = width
        self.height = height
        self._scene_radius_m = scene_radius_m

        terrain_dir = terrain_dir or _PIPELINE_DIR
        import json

        with open(os.path.join(terrain_dir, "metadata.json")) as f:
            self._terrain_meta = json.load(f)

        self._scene_builder = SceneBuilder(
            os.path.join(terrain_dir, "terrain_mesh.obj"),
            os.path.join(terrain_dir, "terrain_texture.png"),
            self._terrain_meta,
        )

        self._camera = DroneCamera(
            width=width,
            height=height,
            focal_length_mm=18.0,
            sensor_width_mm=36.0,
            near=1.0,
            far=50_000_000.0,
        )
        self._renderer = OffscreenRenderer(width, height, prefer_gpu=True)
        self._target_nodes: Dict[int, object] = {}
        self._uav_nodes: Dict[int, object] = {}
        self._drone_marker_mesh = self._build_drone_marker()

    # ---- target / drone placement ------------------------------------------

    def _theater_to_local_cm(
        self, lon: float, lat: float, sim
    ) -> Tuple[float, float]:
        """
        Map theater (lon, lat) coordinates into local terrain coordinates.

        Theater bounds are scaled into a `scene_radius_m`-radius square centred at
        the terrain POI so the sim is visible regardless of theater extent.
        """
        bounds = sim.theater.bounds if hasattr(sim, "theater") else None
        if bounds is None:
            return _lonlat_to_local_cm(
                lon, lat, self._terrain_meta["poi_lon"], self._terrain_meta["poi_lat"]
            )

        # Normalize theater coords to [-1, 1] then scale to scene_radius_m.
        u = 2.0 * (lon - bounds.min_lon) / (bounds.max_lon - bounds.min_lon) - 1.0
        v = 2.0 * (lat - bounds.min_lat) / (bounds.max_lat - bounds.min_lat) - 1.0
        x_cm = u * self._scene_radius_m * 100.0
        z_cm = -v * self._scene_radius_m * 100.0  # north=-z in our convention
        return (x_cm, z_cm)

    def _terrain_y_at(self, x_cm: float, z_cm: float) -> float:
        """Approximate ground height under (x, z). Uses POI elevation as a stand-in."""
        return float(self._terrain_meta.get("poi_local_y_cm", 0.0))

    def sync_targets(self, sim) -> None:
        """Add / move target cubes to match sim.targets exactly."""
        live_ids = set()
        for t in sim.targets.values():
            live_ids.add(t.id)
            x_cm, z_cm = self._theater_to_local_cm(t.x, t.y, sim)
            y_cm = self._terrain_y_at(x_cm, z_cm) + 250.0  # half-height of 5m cube

            target_size = 6000.0  # 60 m cube — visible from km away (oversized for demo)
            name = f"target_{t.id}"
            if t.id not in self._target_nodes:
                self._scene_builder.add_target(
                    name=name,
                    label=t.type,
                    position=np.array([x_cm, y_cm, z_cm]),
                    size=target_size,
                )
                self._target_nodes[t.id] = self._scene_builder._targets[name]["node"]
            else:
                node = self._target_nodes[t.id]
                pose = np.eye(4)
                pose[:3, 3] = [x_cm, y_cm, z_cm]
                self._scene_builder.scene.set_pose(node, pose)

        # Remove stale targets
        stale = [tid for tid in self._target_nodes if tid not in live_ids]
        for tid in stale:
            node = self._target_nodes.pop(tid)
            try:
                self._scene_builder.scene.remove_node(node)
            except Exception:
                pass

    # ---- drone marker ------------------------------------------------------

    def _build_drone_marker(self):
        import trimesh

        # 30 m radius / 12 m high disc — oversized but readable from km away.
        body = trimesh.creation.cylinder(radius=3000, height=1200)
        body.visual.face_colors = [40, 220, 255, 255]
        material = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[0.15, 0.85, 1.0, 1.0],
            metallicFactor=0.6,
            roughnessFactor=0.4,
            emissiveFactor=[0.20, 0.85, 1.0],
        )
        return pyrender.Mesh.from_trimesh(body, material=material)

    def sync_uav_markers(self, sim, exclude_uav_id: Optional[int] = None) -> None:
        """Place small cyan cylinders at every UAV's position (skip the camera-host UAV)."""
        live_ids = set()
        for u in sim.uavs.values():
            if u.id == exclude_uav_id:
                continue
            live_ids.add(u.id)
            x_cm, z_cm = self._theater_to_local_cm(u.x, u.y, sim)
            y_cm = self._terrain_y_at(x_cm, z_cm) + u.altitude_m * 100.0
            pose = np.eye(4)
            pose[:3, 3] = [x_cm, y_cm, z_cm]
            if u.id not in self._uav_nodes:
                node = self._scene_builder.scene.add(self._drone_marker_mesh, pose=pose)
                self._uav_nodes[u.id] = node
            else:
                self._scene_builder.scene.set_pose(self._uav_nodes[u.id], pose)

        # Remove stale UAVs
        stale = [uid for uid in self._uav_nodes if uid not in live_ids]
        for uid in stale:
            node = self._uav_nodes.pop(uid)
            try:
                self._scene_builder.scene.remove_node(node)
            except Exception:
                pass

    # ---- camera control ----------------------------------------------------

    def render_from_uav(
        self,
        sim,
        uav_id: int,
        gimbal_pitch_deg: float = 25.0,
    ) -> np.ndarray:
        """Render the scene from `uav_id`'s gimbal. Returns HxWx3 uint8 RGB."""
        self.sync_targets(sim)
        self.sync_uav_markers(sim, exclude_uav_id=uav_id)

        host = sim.uavs[uav_id]
        x_cm, z_cm = self._theater_to_local_cm(host.x, host.y, sim)
        y_cm = self._terrain_y_at(x_cm, z_cm) + host.altitude_m * 100.0
        # Heading 0° = north (-Z). Convert to forward unit vector in (X east, Z north).
        h = math.radians(host.heading_deg)
        forward = np.array([math.sin(h), 0.0, -math.cos(h)], dtype=np.float64)
        forward /= np.linalg.norm(forward)

        self._camera.set_pose(
            np.array([x_cm, y_cm, z_cm], dtype=np.float64),
            forward,
            gimbal_pitch_deg,
        )
        color, _depth = self._renderer.render(
            self._scene_builder.scene, self._camera
        )
        return color

    def render_overhead(
        self,
        sim,
        altitude_m: float = 4_000.0,
        center: Optional[Tuple[float, float]] = None,
    ) -> np.ndarray:
        """Top-down god-view of the whole battlespace. Useful for debugging integration."""
        self.sync_targets(sim)
        self.sync_uav_markers(sim, exclude_uav_id=None)

        if center is None:
            x_cm, z_cm = 0.0, 0.0
        else:
            x_cm, z_cm = self._theater_to_local_cm(center[0], center[1], sim)
        y_cm = self._terrain_y_at(x_cm, z_cm) + altitude_m * 100.0

        # Look straight down (pitch +90 = nose down)
        self._camera.set_pose(
            np.array([x_cm, y_cm, z_cm], dtype=np.float64),
            np.array([1.0, 0.0, 0.0]),
            89.0,
        )
        color, _depth = self._renderer.render(
            self._scene_builder.scene, self._camera
        )
        return color

    def close(self) -> None:
        try:
            self._renderer.close()
        except Exception:
            pass
