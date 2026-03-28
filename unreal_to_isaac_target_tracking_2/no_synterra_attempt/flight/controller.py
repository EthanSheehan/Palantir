"""Terminal dive flight controller — ported from run_auto.py:370-476."""
import time
from typing import List, Dict, Optional

import numpy as np

from .config import FlightConfig
from .dynamics import Phase, FlightState


class FlightController:
    def __init__(self, config: FlightConfig, target_pos: np.ndarray,
                 flight_dir: np.ndarray = None):
        self.cfg = config
        self.target_pos = np.array(target_pos, dtype=np.float64)
        self.flight_dir = np.array(flight_dir if flight_dir is not None
                                   else [1.0, 0.0, 0.0], dtype=np.float64)

        self._offset = -config.start_offset_cm
        self._pitch = config.initial_pitch
        self._phase = Phase.CRUISE
        self._mission_count = 0
        self._impact_time: Optional[float] = None
        self._tracking = False
        self._error_y = 0.0

        self._pos = np.array([
            self.target_pos[0] + self.flight_dir[0] * self._offset,
            self.target_pos[1] + config.drone_altitude_cm,
            self.target_pos[2],
        ], dtype=np.float64)

    def step(self, dt: float, gt_boxes: List[Dict] = None,
             screen_cy: float = None) -> FlightState:
        if screen_cy is None:
            screen_cy = self.cfg.render_height / 2.0
        if gt_boxes is None:
            gt_boxes = []

        now = time.time()

        # --- TERMINAL phase: hold then reset ---
        if self._phase == Phase.TERMINAL:
            if self._impact_time is None:
                self._impact_time = now
            elif now - self._impact_time >= self.cfg.terminal_hold_sec:
                self._mission_count += 1
                self._offset = -self.cfg.start_offset_cm
                self._pitch = self.cfg.initial_pitch
                self._phase = Phase.CRUISE
                self._impact_time = None
                self._pos[1] = self.target_pos[1] + self.cfg.drone_altitude_cm
                return self._state(should_reset=True)

        # --- Flight physics ---
        self._offset += self.cfg.speed_cm_per_sec * dt
        self._pos[0] = self.target_pos[0] + self.flight_dir[0] * self._offset
        self._pos[2] = self.target_pos[2]
        dist = abs(self._offset)

        if self._phase == Phase.CRUISE:
            self._pos[1] = self.target_pos[1] + self.cfg.drone_altitude_cm
            if dist <= self.cfg.dive_trigger_dist_cm:
                self._phase = Phase.DIVE

        elif self._phase == Phase.DIVE:
            descent = self.cfg.speed_cm_per_sec * np.sin(np.radians(self._pitch))
            self._pos[1] -= descent * dt
            alt = self._pos[1] - self.target_pos[1]
            if alt <= self.cfg.min_altitude_cm:
                self._phase = Phase.TERMINAL

        # --- Pitch guidance ---
        if self._phase == Phase.DIVE and gt_boxes:
            self._tracking = True
            best = max(gt_boxes, key=lambda b:
                       (b["x_max"] - b["x_min"]) * (b["y_max"] - b["y_min"]))
            det_cy = (best["y_min"] + best["y_max"]) / 2
            self._error_y = det_cy - screen_cy
            self._pitch += self.cfg.kp_pitch * self._error_y
            self._pitch = float(np.clip(self._pitch,
                                        self.cfg.min_pitch, self.cfg.max_pitch))
        else:
            self._tracking = len(gt_boxes) > 0
            self._error_y = 0.0

        return self._state()

    def _state(self, should_reset: bool = False) -> FlightState:
        return FlightState(
            position=self._pos.copy(),
            pitch=self._pitch,
            phase=self._phase,
            tracking=self._tracking,
            error_y=self._error_y,
            dist_to_target_cm=abs(self._offset),
            offset_cm=self._offset,
            mission_count=self._mission_count,
            should_reset=should_reset,
        )
