import asyncio
import math
import random
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
import structlog
from coordinate_transformer import pixel_to_gps
from dashboard_connector import DashboardConnector

logger = structlog.get_logger()

EARTH_RADIUS = 6378137.0

# Color and shape config per target type (BGR tuples for OpenCV)
TARGET_STYLES = {
    "SAM": {"color": (0, 0, 255), "shape": "diamond"},
    "TEL": {"color": (0, 140, 255), "shape": "triangle"},
    "TRUCK": {"color": (255, 255, 255), "shape": "rectangle"},
    "CP": {"color": (255, 100, 0), "shape": "square"},
    "MANPADS": {"color": (200, 0, 200), "shape": "small_circle"},
    "RADAR": {"color": (0, 255, 255), "shape": "hexagon"},
    "C2_NODE": {"color": (255, 255, 0), "shape": "diamond"},
    "LOGISTICS": {"color": (180, 180, 180), "shape": "rectangle"},
}

DEFAULT_STYLE = {"color": (0, 200, 0), "shape": "square"}


def gps_to_pixel(
    target_lon: float,
    target_lat: float,
    drone_lat: float,
    drone_lon: float,
    drone_alt: float,
    gimbal_pitch: float,
    gimbal_yaw: float,
    image_width: int,
    image_height: int,
    hfov: float = 60.0,
) -> Optional[tuple[int, int]]:
    """Convert GPS (lon, lat) to pixel (x, y) relative to drone camera.

    Returns None if the target falls outside the camera FOV.
    """
    pitch_rad = math.radians(gimbal_pitch if gimbal_pitch < -1 else -1)
    yaw_rad = math.radians(gimbal_yaw)
    hfov_rad = math.radians(hfov)
    aspect_ratio = image_width / image_height
    vfov_rad = 2 * math.atan(math.tan(hfov_rad / 2) / aspect_ratio)

    dist_at_center = drone_alt / math.sin(abs(pitch_rad))

    # GPS delta to meter offsets
    delta_lat = target_lat - drone_lat
    delta_lon = target_lon - drone_lon

    offset_n = delta_lat * (math.pi / 180) * EARTH_RADIUS
    offset_e = delta_lon * (math.pi / 180) * EARTH_RADIUS * math.cos(math.radians(drone_lat))

    # Reverse yaw rotation to get local camera-frame offsets
    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)
    offset_x_local = offset_e * cos_yaw - offset_n * sin_yaw
    offset_y_local = offset_e * sin_yaw + offset_n * cos_yaw

    # Reverse pitch compensation on y
    offset_y_local = offset_y_local * math.cos(math.radians(gimbal_pitch + 90))

    # Convert meter offsets to angular offsets
    if dist_at_center < 1.0:
        return None

    angle_x = math.atan2(offset_x_local, dist_at_center)
    angle_y = math.atan2(offset_y_local, dist_at_center)

    # Check if within FOV
    if abs(angle_x) > hfov_rad / 2 or abs(angle_y) > vfov_rad / 2:
        return None

    # Angular offset to normalized coords
    norm_x = angle_x / hfov_rad + 0.5
    norm_y = 0.5 - angle_y / vfov_rad

    px = int(norm_x * image_width)
    py = int(norm_y * image_height)

    if px < 0 or px >= image_width or py < 0 or py >= image_height:
        return None

    return (px, py)


def _calculate_range_m(drone_lat, drone_lon, target_lat, target_lon):
    """Haversine distance in meters between two GPS points."""
    lat1, lat2 = math.radians(drone_lat), math.radians(target_lat)
    dlat = lat2 - lat1
    dlon = math.radians(target_lon - drone_lon)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _calculate_bearing_deg(drone_lat, drone_lon, target_lat, target_lon):
    """Bearing in degrees from drone to target."""
    lat1, lat2 = math.radians(drone_lat), math.radians(target_lat)
    dlon = math.radians(target_lon - drone_lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


class MissionScenario:
    def __init__(self, name="Default"):
        self.name = name

    def update_drone(self, drone, dt):
        pass


class ScanningScenario(MissionScenario):
    """Drone flies in a lawnmower or circular pattern."""

    def __init__(self, pattern="circular"):
        super().__init__(f"Scanning-{pattern}")
        self.pattern = pattern
        self.angle = 0
        self.radius = 150
        self.center_x = 0
        self.center_y = 0

    def update_drone(self, drone, dt):
        if self.pattern == "circular":
            self.angle += dt * 0.5
            drone["lat"] = drone["origin_lat"] + (math.cos(self.angle) * 0.001)
            drone["lon"] = drone["origin_lon"] + (math.sin(self.angle) * 0.001)
            drone["yaw"] = (math.degrees(-self.angle) + 90) % 360


class TrackingScenario(MissionScenario):
    """Drone follows a specific target."""

    def __init__(self, target_id):
        super().__init__(f"Tracking-{target_id}")
        self.target_id = target_id

    def update_drone(self, drone, dt, blocks):
        target = next((b for b in blocks if b["id"] == self.target_id), None)
        if not target:
            return

        target_lat = target["lat"]
        target_lon = target["lon"]

        bearing_deg = _calculate_bearing_deg(drone["lat"], drone["lon"], target_lat, target_lon)
        range_m = _calculate_range_m(drone["lat"], drone["lon"], target_lat, target_lon)

        drone["yaw"] = bearing_deg

        speed_ms = drone.get("speed", 15.0)
        step_m = min(speed_ms * dt, range_m)

        if range_m < 1.0:
            return

        bearing_rad = math.radians(bearing_deg)
        d_lat = (step_m / EARTH_RADIUS) * math.cos(bearing_rad)
        d_lon = (step_m / EARTH_RADIUS) * math.sin(bearing_rad) / math.cos(math.radians(drone["lat"]))

        drone["lat"] = drone["lat"] + math.degrees(d_lat)
        drone["lon"] = drone["lon"] + math.degrees(d_lon)


class PaintingScenario(MissionScenario):
    """Drone orbits and 'paints' (locks onto) a specific target."""

    def __init__(self, target_id):
        super().__init__(f"Painting-{target_id}")
        self.target_id = target_id
        self.angle = 0

    def update_drone(self, drone, dt):
        self.angle += dt * 0.3
        # Orbit around a fixed point representing the target
        drone["lat"] = drone["origin_lat"] + (math.cos(self.angle) * 0.0005)
        drone["lon"] = drone["origin_lon"] + (math.sin(self.angle) * 0.0005)
        # Always face the center (the target)
        drone["yaw"] = (math.degrees(-self.angle)) % 360


class DroneSimulator:
    def __init__(self, drone_id, origin_lat=51.4545, origin_lon=-2.5879, width=800, height=600, fps=12):
        self.drone_id = drone_id
        self.width = width
        self.height = height
        self.fps = fps
        self.connector = DashboardConnector(backend_url="ws://localhost:8000/ws")

        self.state = {
            "lat": origin_lat,
            "lon": origin_lon,
            "origin_lat": origin_lat,
            "origin_lon": origin_lon,
            "alt": 120.0,
            "pitch": -45.0,
            "yaw": 0.0,
            "speed": 15.0,  # m/s mock
        }

        self.scenario = ScanningScenario(pattern="circular")

        # Simulated "Blocks" (fallback targets when not connected to sim_engine)
        self.blocks = [
            {
                "id": "CP-1",
                "x": random.randint(100, 700),
                "y": random.randint(100, 500),
                "vx": 2,
                "vy": 1,
                "color": (0, 0, 255),
                "type": "TEL",
            },
            {
                "id": "CP-2",
                "x": random.randint(100, 700),
                "y": random.randint(100, 500),
                "vx": -1,
                "vy": 2,
                "color": (255, 0, 0),
                "type": "CP",
            },
        ]

        # Real targets from sim_engine (immutable — replaced each update)
        self._sim_targets: tuple[dict, ...] = ()
        # Drone mode from sim_engine
        self._drone_mode: str = "SEARCH"
        self._tracked_target_id: Optional[int] = None
        # Lock pulse animation state
        self._lock_pulse_phase: float = 0.0
        # Sensor range in meters
        self._sensor_range_m: float = 15000.0
        # Camera horizontal FOV in degrees
        self._camera_hfov: float = 60.0

    def update_targets(self, targets: list[dict]) -> None:
        """Receive current target positions from sim_engine.

        Each target dict has: id, lon, lat, type, state, heading_deg,
        plus optional: detection_confidence, is_emitting, tracked_by_uav_id.
        """
        self._sim_targets = tuple(targets)

    def update_drone_mode(self, mode: str, tracked_target_id: Optional[int] = None) -> None:
        """Update drone mode and tracked target from sim_engine state."""
        self._drone_mode = mode
        self._tracked_target_id = tracked_target_id

    @property
    def _has_sim_targets(self) -> bool:
        return len(self._sim_targets) > 0

    @property
    def _is_tracking(self) -> bool:
        return self._drone_mode in ("VIEWING", "FOLLOWING", "PAINTING")

    def _find_tracked_target(self) -> Optional[dict]:
        if self._tracked_target_id is None:
            return None
        for t in self._sim_targets:
            if t.get("id") == self._tracked_target_id:
                return t
        return None

    def _draw_target_shape(self, frame, px, py, target_type, size=18):
        """Draw type-specific shape at pixel position."""
        style = TARGET_STYLES.get(target_type, DEFAULT_STYLE)
        color = style["color"]
        shape = style["shape"]
        s = size

        if shape == "diamond":
            pts = np.array([[px, py - s], [px + s, py], [px, py + s], [px - s, py]], np.int32)
            cv2.polylines(frame, [pts], True, color, 2)

        elif shape == "triangle":
            pts = np.array([[px, py - s], [px + s, py + s], [px - s, py + s]], np.int32)
            cv2.polylines(frame, [pts], True, color, 2)

        elif shape == "rectangle":
            cv2.rectangle(frame, (px - s, py - s // 2), (px + s, py + s // 2), color, 2)

        elif shape == "square":
            cv2.rectangle(frame, (px - s, py - s), (px + s, py + s), color, 2)

        elif shape == "small_circle":
            cv2.circle(frame, (px, py), s // 2, color, 2)

        elif shape == "hexagon":
            pts = np.array(
                [
                    [px + int(s * math.cos(math.radians(a))), py + int(s * math.sin(math.radians(a)))]
                    for a in range(0, 360, 60)
                ],
                np.int32,
            )
            cv2.polylines(frame, [pts], True, color, 2)

    def _draw_corner_markers(self, frame, bx, by, half_w, half_h, color, cl=10):
        """Draw tactical corner brackets around a bounding box."""
        corners = [
            (bx - half_w, by - half_h, 1, 1),
            (bx + half_w, by - half_h, -1, 1),
            (bx - half_w, by + half_h, 1, -1),
            (bx + half_w, by + half_h, -1, -1),
        ]
        for cx, cy, dx, dy in corners:
            cv2.line(frame, (cx, cy), (cx + cl * dx, cy), color, 2)
            cv2.line(frame, (cx, cy), (cx, cy + cl * dy), color, 2)

    def _draw_targeting_reticle(self, frame, px, py):
        """Draw crosshair reticle centered on tracked target."""
        color = (0, 255, 0)
        gap = 12
        arm = 30
        # Four arms with gap in center
        cv2.line(frame, (px - arm, py), (px - gap, py), color, 1)
        cv2.line(frame, (px + gap, py), (px + arm, py), color, 1)
        cv2.line(frame, (px, py - arm), (px, py - gap), color, 1)
        cv2.line(frame, (px, py + arm), (px, py + gap), color, 1)
        # Small tick marks
        for d in (-arm, arm):
            cv2.line(frame, (px + d, py - 4), (px + d, py + 4), color, 1)
            cv2.line(frame, (px - 4, py + d), (px + 4, py + d), color, 1)

    def _draw_lock_indicator(self, frame, px, py, dt):
        """Draw pulsing red lock box around target for PAINTING mode."""
        self._lock_pulse_phase += dt * 4.0
        pulse = 0.5 + 0.5 * math.sin(self._lock_pulse_phase)
        intensity = int(128 + 127 * pulse)
        color = (0, 0, intensity)
        size = int(30 + 8 * pulse)
        thickness = max(1, int(1 + 2 * pulse))

        cv2.rectangle(
            frame,
            (px - size, py - size),
            (px + size, py + size),
            color,
            thickness,
        )
        # Inner brackets
        self._draw_corner_markers(frame, px, py, size - 4, size - 4, color, cl=8)

    def _draw_target_info_overlay(self, frame, target, range_m, bearing_deg):
        """Draw target info panel in bottom-left for tracked target."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        color = (0, 255, 0)
        x_start = 30
        y_start = self.height - 120

        lines = [
            f"TGT: {target.get('type', '?')} #{target.get('id', '?')}",
            f"STATE: {target.get('state', '?')}",
            f"CONF: {target.get('detection_confidence', 0):.2f}",
            f"RNG: {range_m:.0f}m  BRG: {bearing_deg:.1f}",
        ]
        if target.get("is_emitting"):
            lines.append("EMITTING: YES")

        # Background panel
        panel_h = len(lines) * 20 + 10
        overlay = frame.copy()
        cv2.rectangle(overlay, (x_start - 5, y_start - 15), (x_start + 260, y_start + panel_h - 15), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        for i, line in enumerate(lines):
            cv2.putText(frame, line, (x_start, y_start + i * 20), font, 0.45, color, 1)

    def draw_hud(self, frame, dt=0.0):
        color = (0, 255, 0)
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Corner brackets
        length = 40
        cv2.line(frame, (20, 20), (20 + length, 20), color, 1)
        cv2.line(frame, (20, 20), (20, 20 + length), color, 1)
        cv2.line(frame, (self.width - 20, 20), (self.width - 20 - length, 20), color, 1)
        cv2.line(frame, (self.width - 20, 20), (self.width - 20, 20 + length), color, 1)
        cv2.line(frame, (20, self.height - 20), (20 + length, self.height - 20), color, 1)
        cv2.line(frame, (20, self.height - 20), (20, self.height - 20 - length), color, 1)
        cv2.line(frame, (self.width - 20, self.height - 20), (self.width - 20 - length, self.height - 20), color, 1)
        cv2.line(frame, (self.width - 20, self.height - 20), (self.width - 20, self.height - 20 - length), color, 1)

        # Telemetry (top-left)
        cv2.putText(frame, f"ID: {self.drone_id}", (30, 40), font, 0.5, color, 1)
        cv2.putText(frame, f"ALT: {self.state['alt']:.1f}M", (30, 60), font, 0.5, color, 1)
        cv2.putText(frame, f"YAW: {self.state['yaw']:.1f}", (30, 80), font, 0.5, color, 1)

        # Drone mode (top-left, below telemetry)
        mode_str = self._drone_mode if self._has_sim_targets else self.scenario.name
        mode_color = color
        if self._drone_mode == "PAINTING":
            mode_color = (0, 0, 255)
        elif self._drone_mode in ("VIEWING", "FOLLOWING"):
            mode_color = (0, 200, 255)
        cv2.putText(frame, f"MODE: {mode_str}", (30, 100), font, 0.5, mode_color, 1)

        # Position (top-right)
        pos_str = f"L: {self.state['lat']:.5f} N, {self.state['lon']:.5f} E"
        cv2.putText(frame, pos_str, (self.width - 250, 40), font, 0.5, color, 1)

        # Tracking info (top-right, below position)
        tracked = self._find_tracked_target() if self._has_sim_targets else None
        if tracked and self._is_tracking:
            range_m = _calculate_range_m(
                self.state["lat"],
                self.state["lon"],
                tracked["lat"],
                tracked["lon"],
            )
            bearing = _calculate_bearing_deg(
                self.state["lat"],
                self.state["lon"],
                tracked["lat"],
                tracked["lon"],
            )
            cv2.putText(
                frame,
                f"TRK: {tracked.get('type', '?')} #{tracked['id']}",
                (self.width - 250, 60),
                font,
                0.45,
                mode_color,
                1,
            )
            cv2.putText(
                frame,
                f"RNG: {range_m:.0f}m  BRG: {bearing:.1f}",
                (self.width - 250, 78),
                font,
                0.45,
                mode_color,
                1,
            )
            if self._drone_mode == "PAINTING":
                cv2.putText(
                    frame,
                    "LOCK: ACTIVE",
                    (self.width - 250, 96),
                    font,
                    0.45,
                    (0, 0, 255),
                    1,
                )

        # Center crosshair — changes based on mode
        cx, cy = self.width // 2, self.height // 2

        if self._has_sim_targets and self._drone_mode == "PAINTING":
            pass  # Lock indicator drawn separately on target
        elif isinstance(self.scenario, PaintingScenario) and not self._has_sim_targets:
            paint_color = (0, 0, 255)
            cv2.putText(frame, "TARGET LOCKED - PAINTING", (cx - 100, cy - 40), font, 0.6, paint_color, 2)
            cv2.drawMarker(frame, (cx, cy), paint_color, cv2.MARKER_TILTED_CROSS, 20, 2)
        else:
            cv2.line(frame, (cx - 10, cy), (cx + 10, cy), color, 1)
            cv2.line(frame, (cx, cy - 10), (cx, cy + 10), color, 1)

    def _render_sim_targets(self, frame, dt):
        """Render real sim_engine targets projected into camera view."""
        detections = []
        tracked = self._find_tracked_target()

        for target in self._sim_targets:
            t_lon = target["lon"]
            t_lat = target["lat"]
            t_type = target.get("type", "UNKNOWN")
            t_id = target["id"]
            t_state = target.get("state", "DETECTED")

            # Range check
            range_m = _calculate_range_m(
                self.state["lat"],
                self.state["lon"],
                t_lat,
                t_lon,
            )
            if range_m > self._sensor_range_m:
                continue

            # If tracking, center camera on tracked target by adjusting yaw
            if tracked and tracked["id"] == t_id and self._is_tracking:
                # Override yaw to point at tracked target
                bearing = _calculate_bearing_deg(
                    self.state["lat"],
                    self.state["lon"],
                    t_lat,
                    t_lon,
                )
                self.state["yaw"] = bearing

            pixel = gps_to_pixel(
                t_lon,
                t_lat,
                self.state["lat"],
                self.state["lon"],
                self.state["alt"],
                self.state["pitch"],
                self.state["yaw"],
                self.width,
                self.height,
                self._camera_hfov,
            )
            if pixel is None:
                continue

            px, py = pixel
            style = TARGET_STYLES.get(t_type, DEFAULT_STYLE)
            color = style["color"]

            # Draw target shape
            self._draw_target_shape(frame, px, py, t_type)

            # Bounding box with corner markers
            half_w, half_h = 22, 22
            self._draw_corner_markers(frame, px, py, half_w, half_h, color)

            # Crosshair in target
            cv2.line(frame, (px - 5, py), (px + 5, py), color, 1)
            cv2.line(frame, (px, py - 5), (px, py + 5), color, 1)

            # Label
            conf = target.get("detection_confidence", 0.92)
            label = f"{t_type} #{t_id} [{conf:.2f}]"
            cv2.putText(frame, label, (px - half_w, py - half_h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            # Tracking overlays
            is_this_tracked = tracked and tracked["id"] == t_id
            if is_this_tracked and self._is_tracking:
                self._draw_targeting_reticle(frame, px, py)
                bearing = _calculate_bearing_deg(
                    self.state["lat"],
                    self.state["lon"],
                    t_lat,
                    t_lon,
                )
                self._draw_target_info_overlay(frame, target, range_m, bearing)

                if self._drone_mode == "PAINTING":
                    self._draw_lock_indicator(frame, px, py, dt)

            detections.append(
                {
                    "id": t_id,
                    "type": t_type,
                    "metadata": {
                        "affiliation": "OPFOR",
                        "source": self.drone_id,
                    },
                    "kinematics": {
                        "latitude": t_lat,
                        "longitude": t_lon,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "kill_chain_state": "LOCK" if self._drone_mode == "PAINTING" and is_this_tracked else "TRACK",
                    "confidence_score": conf,
                }
            )

        return detections

    def _render_fallback_blocks(self, frame):
        """Render legacy random blocks when sim_engine targets are unavailable."""
        detections = []
        for block in self.blocks:
            block["x"] = (block["x"] + block["vx"]) % self.width
            block["y"] = (block["y"] + block["vy"]) % self.height

            bx, by = int(block["x"]), int(block["y"])
            bw, bh = 40, 40
            cv2.rectangle(frame, (bx - bw // 2, by - bh // 2), (bx + bw // 2, by + bh // 2), block["color"], 1)

            self._draw_corner_markers(frame, bx, by, bw // 2, bh // 2, block["color"])

            cv2.line(frame, (bx - 5, by), (bx + 5, by), block["color"], 1)
            cv2.line(frame, (bx, by - 5), (bx, by + 5), block["color"], 1)

            conf = 0.92 + (random.random() * 0.05)
            label = f"{block['type']} [{conf:.2f}]"
            cv2.putText(
                frame, label, (bx - bw // 2, by - bh // 2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, block["color"], 1
            )

            lat, lon = pixel_to_gps(
                block["x"],
                block["y"],
                self.width,
                self.height,
                self.state["lat"],
                self.state["lon"],
                self.state["alt"],
                self.state["pitch"],
                self.state["yaw"],
            )

            detections.append(
                {
                    "id": block["id"],
                    "type": block["type"],
                    "metadata": {"affiliation": "OPFOR", "source": self.drone_id},
                    "kinematics": {"latitude": lat, "longitude": lon, "timestamp": datetime.now().isoformat()},
                    "kill_chain_state": "LOCK" if isinstance(self.scenario, PaintingScenario) else "TRACK",
                    "confidence_score": 0.98 if isinstance(self.scenario, PaintingScenario) else conf,
                }
            )

        return detections

    def create_frame(self, dt: float = 0.0):
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (20, 25, 20)

        # Subtle grid
        for i in range(0, self.width, 100):
            cv2.line(frame, (i, 0), (i, self.height), (30, 35, 30), 1)
        for i in range(0, self.height, 100):
            cv2.line(frame, (0, i), (self.width, i), (30, 35, 30), 1)

        if self._has_sim_targets:
            detections = self._render_sim_targets(frame, dt)
        else:
            detections = self._render_fallback_blocks(frame)

        self.draw_hud(frame, dt)
        return frame, detections

    async def run(self):
        log = logger.bind(drone_id=self.drone_id)
        log.info("drone_simulator_starting")
        await self.connector.connect()

        dt = 1.0 / self.fps
        tick_count = 0
        try:
            while True:
                tick_count += 1
                start_time = asyncio.get_event_loop().time()

                # Check for incoming commands
                cmd = await self.connector.receive_command()
                if cmd and cmd.get("type") == "CMD_SET_SCENARIO":
                    scenario_name = cmd.get("scenario")
                    drone_target = cmd.get("drone_id")

                    if drone_target == self.drone_id or drone_target == "ALL":
                        log.info("scenario_command_received", scenario=scenario_name)
                        if scenario_name == "PAINTING":
                            target_id = f"{self.drone_id}-TGT-PAINTED"
                            self.blocks = [
                                {
                                    "id": target_id,
                                    "x": 320,
                                    "y": 240,
                                    "vx": 0,
                                    "vy": 0,
                                    "color": (0, 0, 255),
                                    "type": "TGT",
                                }
                            ]
                            self.scenario = PaintingScenario(target_id)
                        elif scenario_name == "DISCOVERY":
                            self.scenario = ScanningScenario(pattern="circular")
                        self.blocks = [
                            {
                                "id": "CP-1",
                                "x": random.randint(100, 700),
                                "y": random.randint(100, 500),
                                "vx": 2,
                                "vy": 1,
                                "color": (255, 100, 0),
                                "type": "TEL",
                            },
                            {
                                "id": "CP-2",
                                "x": random.randint(100, 700),
                                "y": random.randint(100, 500),
                                "vx": -1,
                                "vy": 2,
                                "color": (0, 150, 255),
                                "type": "CP",
                            },
                            {
                                "id": "TGT-ALPHA",
                                "x": random.randint(100, 700),
                                "y": random.randint(100, 500),
                                "vx": 1,
                                "vy": -1,
                                "color": (0, 0, 255),
                                "type": "SAM",
                            },
                            {
                                "id": "TGT-BRAVO",
                                "x": random.randint(100, 700),
                                "y": random.randint(100, 500),
                                "vx": -2,
                                "vy": 0.5,
                                "color": (0, 255, 255),
                                "type": "TRUCK",
                            },
                        ]

                # Update scenario (only used when not connected to sim_engine)
                if not self._has_sim_targets:
                    self.scenario.update_drone(self.state, dt)

                # Generate frame and data
                frame, detections = self.create_frame(dt)

                # Push drone's own telemetry as a UAV track
                drone_track = {
                    "id": self.drone_id,
                    "type": "UAV",
                    "kinematics": {
                        "latitude": self.state["lat"],
                        "longitude": self.state["lon"],
                        "timestamp": datetime.now().isoformat(),
                    },
                    "metadata": {"affiliation": "FRIENDLY", "altitude": self.state["alt"], "yaw": self.state["yaw"]},
                }
                try:
                    all_tracks = [drone_track] + detections

                    await self.connector.send_telemetry_batch(all_tracks, drone_id=self.drone_id)

                    if tick_count % 3 == 0:  # ~3.3 FPS
                        await self.connector.stream_frame(frame, drone_id=self.drone_id)

                    elapsed = asyncio.get_event_loop().time() - start_time
                    await asyncio.sleep(max(0, dt - elapsed))
                except (asyncio.TimeoutError, ConnectionError, OSError) as exc:
                    error_str = str(exc).lower()
                    if "1011" in error_str or "timeout" in error_str or "keepalive" in error_str:
                        log.warning("transient_ws_error", error=str(exc))
                    else:
                        log.error("connection_lost_retrying", error=str(exc))
                        await asyncio.sleep(5)
                        break  # Exit the inner while to trigger the outer reconnect

        except (ConnectionError, OSError) as exc:
            log.error("global_error", error=str(exc))
            await self.connector.close()
            await asyncio.sleep(5)
            await self.connector.connect()
            log.info("reconnected")
        finally:
            await self.connector.close()


async def main():
    # Multi-drone simulation with reduced load in Romania
    drones = [
        DroneSimulator("0", origin_lat=45.9432, origin_lon=24.9668, fps=8),
        DroneSimulator("1", origin_lat=46.1000, origin_lon=25.2000, fps=8),
    ]

    # Change scenario for the second drone
    drones[1].scenario = ScanningScenario(pattern="circular")
    drones[1].state["alt"] = 150.0

    await asyncio.gather(*(d.run() for d in drones))


if __name__ == "__main__":
    asyncio.run(main())
