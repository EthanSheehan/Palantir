"""
pyrender_mock.py
================
MockGridSentinelRenderer — drop-in for GridSentinelRenderer on systems that
can't open an OpenGL context (macOS in headless shell, CI runners without
DISPLAY, etc.).

Renders the same SimulationModel state (UAVs, targets, theater) through
matplotlib so the frontend integration path can be exercised end-to-end
without pyrender's pyglet/EGL dependencies. The output is a 3D top-down view
of the theater with target markers + UAV positions colour-coded the same way
the real pyrender path renders them.

Activated by setting USE_PYRENDER_MOCK=true in tandem with USE_PYRENDER=true.
The real GridSentinelRenderer remains the production code path.
"""
from __future__ import annotations

import io
import math
from typing import Dict, Tuple

import numpy as np

try:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle, Polygon as MplPolygon
    _MPL_OK = True
except ImportError:
    _MPL_OK = False


# Mirror src/python/vision/video_simulator.py TARGET_STYLES so the mock view
# matches the colours the rest of Grid-Sentinel uses for targets.
_TARGET_COLORS: Dict[str, str] = {
    "SAM":       "#f21a1a",
    "TEL":       "#ff8c1a",
    "TRUCK":     "#f2f2f2",
    "CP":        "#3373ff",
    "MANPADS":   "#c633c6",
    "RADAR":     "#33f2f2",
    "C2_NODE":   "#f2f233",
    "LOGISTICS": "#b3b3b3",
    "ARTILLERY": "#ff4d8c",
    "APC":       "#665033",
}


class MockGridSentinelRenderer:
    """matplotlib-backed stand-in for GridSentinelRenderer."""

    def __init__(self, width: int = 640, height: int = 480):
        if not _MPL_OK:
            raise RuntimeError("matplotlib not installed — install matplotlib to use MockGridSentinelRenderer")
        self.width = width
        self.height = height

    # ------------------------------------------------------------------
    def _theater_extent(self, sim) -> Tuple[float, float, float, float]:
        b = getattr(sim, "theater", None)
        bounds = getattr(b, "bounds", None) if b else None
        if bounds is None:
            return (-1.0, 1.0, -1.0, 1.0)
        return (bounds.min_lon, bounds.max_lon, bounds.min_lat, bounds.max_lat)

    # ------------------------------------------------------------------
    def render_from_uav(self, sim, uav_id: int, gimbal_pitch_deg: float = 25.0) -> np.ndarray:
        """Render a gimbal-POV stand-in: a focused view centred on the host UAV
        with the target field laid out around it."""
        host = sim.uavs[uav_id]
        min_lon, max_lon, min_lat, max_lat = self._theater_extent(sim)

        dpi = 100
        fig = Figure(figsize=(self.width / dpi, self.height / dpi), dpi=dpi)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1a2433")
        fig.patch.set_facecolor("#0d1117")

        # Synthetic sky → horizon → ground gradient
        for y_frac, c in [(0.55, "#1a2433"), (0.50, "#3a4a5e"), (0.0, "#2d4a2d")]:
            ax.add_patch(Rectangle((0, y_frac * self.height), self.width,
                                   (1.0 - y_frac) * self.height,
                                   facecolor=c, zorder=0))
        # Ground "perspective" grid
        for k in range(8):
            y = 0.50 - 0.05 * k
            ax.plot([self.width * (0.5 - 0.5 * (1 - k / 8.0)),
                     self.width * (0.5 + 0.5 * (1 - k / 8.0))],
                    [y * self.height, y * self.height],
                    color="#4a5e7a", linewidth=0.5, zorder=1)

        # Project each entity in the world from the host UAV's frame.
        # Entities are at (lon, lat) in degrees — convert dlon, dlat to metres
        # via a flat-earth approximation at the host's latitude, then run a
        # simple pinhole projection with HFOV ≈ 60°.
        h = math.radians(host.heading_deg)
        # 1° lat ≈ 111 km; 1° lon ≈ 111 km · cos(lat). Mock units are dimensionless
        # we just need them consistent so targets distribute across the frustum.
        lat_m_per_deg = 111_000.0
        lon_m_per_deg = 111_000.0 * math.cos(math.radians(host.y))
        focal = self.width / (2.0 * math.tan(math.radians(30.0)))  # 60° HFOV

        def _project(entity_lon: float, entity_lat: float):
            dlon_m = (entity_lon - host.x) * lon_m_per_deg
            dlat_m = (entity_lat - host.y) * lat_m_per_deg
            # Camera frame: x right, y up, +z forward (along heading)
            cam_x = math.cos(h) * dlon_m - math.sin(h) * dlat_m
            cam_z = math.sin(h) * dlon_m + math.cos(h) * dlat_m
            if cam_z <= 100.0:
                return None
            # Pitch: assume gimbal tilted down by gimbal_pitch_deg; project
            # vertical offset proportionally.
            ground_pitch_rad = math.radians(gimbal_pitch_deg)
            px = self.width * 0.5 + (cam_x / cam_z) * focal
            # Targets sit on the ground; their image-plane y depends on slant range
            # and pitch — closer targets near bottom, distant ones near horizon.
            y_norm = max(0.0, min(1.0, math.atan(host.altitude_m / cam_z) / ground_pitch_rad))
            py = self.height * (0.50 + 0.40 * y_norm)
            return px, py, cam_z

        for t in sim.targets.values():
            proj = _project(t.x, t.y)
            if not proj:
                continue
            px, py, depth = proj
            if not (0 < px < self.width and 0 < py < self.height):
                continue
            color = _TARGET_COLORS.get(t.type, "#ffd633")
            # Size attenuates with depth
            size = max(40, min(260, int(60_000.0 / max(depth, 100.0))))
            ax.scatter([px], [py], s=size, c=color,
                       edgecolor="white", linewidth=1.2,
                       marker="s", zorder=10)
            ax.text(px + 8, py - 6, f"{t.type}", color="white",
                    fontsize=7, family="monospace", zorder=11,
                    bbox=dict(facecolor="black", alpha=0.6,
                              edgecolor=color, boxstyle="round,pad=0.2"))

        for u in sim.uavs.values():
            if u.id == uav_id:
                continue
            proj = _project(u.x, u.y)
            if not proj:
                continue
            px, py, _ = proj
            if not (0 < px < self.width and 0 < py < self.height):
                continue
            ax.scatter([px], [py], s=80, c="#58a6ff",
                       edgecolor="white", linewidth=0.8,
                       marker="o", zorder=9)

        # HUD overlay
        ax.text(8, 12, f"PYRENDER · MOCK · DRONE #{uav_id}",
                color="#58a6ff", fontsize=8, family="monospace",
                bbox=dict(facecolor="black", alpha=0.7, edgecolor="#58a6ff", boxstyle="round,pad=0.3"))
        ax.text(8, 30, f"hdg {host.heading_deg:.0f}°  alt {host.altitude_m:.0f}m  pitch {gimbal_pitch_deg:.0f}°",
                color="#7ee787", fontsize=7, family="monospace")
        ax.text(8, 44, f"targets: {len(sim.targets)}  uavs: {len(sim.uavs)}",
                color="#e3b341", fontsize=7, family="monospace")
        # Crosshair
        cx, cy = self.width / 2, self.height / 2
        for dx, dy in [(-12, 0), (12, 0), (0, -12), (0, 12)]:
            ax.plot([cx, cx + dx], [cy, cy + dy], color="#7ee787", linewidth=1.0, zorder=20)
        ax.plot([cx], [cy], "+", color="#7ee787", markersize=10, zorder=20)

        ax.set_xlim(0, self.width)
        ax.set_ylim(self.height, 0)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)

        canvas.draw()
        buf = io.BytesIO()
        canvas.print_png(buf)
        # Convert PNG bytes to ndarray (3 channels)
        from PIL import Image
        buf.seek(0)
        img = np.array(Image.open(buf).convert("RGB"))
        return img

    def render_overhead(self, sim, altitude_m: float = 4000.0, center=None) -> np.ndarray:
        return self.render_from_uav(sim, next(iter(sim.uavs)), 89.0)

    def close(self):
        pass
