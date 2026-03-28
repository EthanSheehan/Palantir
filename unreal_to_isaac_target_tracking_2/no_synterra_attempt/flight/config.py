"""Flight configuration — all tunable parameters from run_auto.py."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FlightConfig:
    render_width: int = 640
    render_height: int = 480
    drone_altitude_cm: float = 10000.0        # 100m
    start_offset_cm: float = 30000.0          # 300m
    dive_trigger_dist_cm: float = 15000.0     # 150m
    speed_cm_per_sec: float = 1388.9          # 50 kph
    initial_pitch: float = 0.0
    kp_pitch: float = 0.15                    # deg/pixel
    min_pitch: float = 5.0
    max_pitch: float = 85.0
    min_altitude_cm: float = 200.0            # 2m impact threshold
    focal_length_mm: float = 18.0
    sensor_width_mm: float = 36.0
    near_clip_cm: float = 1.0
    far_clip_cm: float = 50000000.0           # 500km
    max_frames: int = 20000
    terminal_hold_sec: float = 1.0
