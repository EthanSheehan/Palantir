"""
multi_int_simulator.py
======================
Synthesise plausible SAR / SIGINT / MTI / GEOINT contributions alongside the
existing EO/IR-driven detections. Used by the IntelLayerPanel so per-INT
toggles have *real* per-INT data to filter on, rather than every detection
being labelled EO_IR.

Each tick attaches an extra `SensorContribution` to a target when the
modality's coverage / time-of-day / weather rules permit. Drives `sim_engine`
fusion the same way the EO contributions do today — `sensor_fusion.fuse_detections`
already handles per-type max deduplication.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional


@dataclass(frozen=True)
class SyntheticContribution:
    """Mirrors the dict shape sensor_fusion expects in `sensor_contributions`."""
    uav_id: int
    sensor_type: str
    confidence: float
    range_m: float
    bearing_deg: float
    timestamp: float
    source_kind: str  # e.g. "ICEYE-X-band", "SIGINT-RFEMITTER-S-band"


@dataclass
class IntStreamConfig:
    """Static rules for a synthetic INT stream."""
    sensor_type: str
    base_confidence: float
    weather_sensitivity: float  # 0=immune, 1=fully degraded
    requires_emitter: bool = False
    daytime_only: bool = False
    range_max_km: float = 250.0
    source_kinds: tuple[str, ...] = ()


SAR_CONFIG = IntStreamConfig(
    sensor_type="SAR",
    base_confidence=0.72,
    weather_sensitivity=0.10,    # SAR sees through cloud
    range_max_km=400.0,
    source_kinds=("ICEYE-X-band", "Capella-X-band", "Umbra-S-band"),
)

SIGINT_CONFIG = IntStreamConfig(
    sensor_type="SIGINT",
    base_confidence=0.78,
    weather_sensitivity=0.0,
    requires_emitter=True,
    range_max_km=600.0,
    source_kinds=("RFEMITTER-S-band", "RFEMITTER-X-band", "COMINT-VHF"),
)

MTI_CONFIG = IntStreamConfig(
    sensor_type="MTI",
    base_confidence=0.65,
    weather_sensitivity=0.30,
    range_max_km=300.0,
    source_kinds=("AESA-MTI", "GMTI-airborne"),
)

GEOINT_CONFIG = IntStreamConfig(
    sensor_type="GEO",
    base_confidence=0.55,
    weather_sensitivity=0.20,
    daytime_only=True,
    range_max_km=10_000.0,
    source_kinds=("Maxar-WV3", "Planet-SkySat", "Keyhole-class"),
)

DEFAULT_STREAMS: tuple[IntStreamConfig, ...] = (SAR_CONFIG, SIGINT_CONFIG, MTI_CONFIG, GEOINT_CONFIG)


@dataclass
class MultiIntSimulator:
    """Stateless-ish wrapper. Call `extra_contributions(target, uavs)` per tick."""
    weather_factor: float = 0.0    # 0.0 clear, 1.0 full overcast
    is_daytime: bool = True
    streams: tuple[IntStreamConfig, ...] = field(default_factory=lambda: DEFAULT_STREAMS)
    rng: random.Random = field(default_factory=lambda: random.Random())

    def extra_contributions(
        self,
        target,
        uavs: Iterable,
    ) -> list[dict]:
        """Return any synthesised SensorContribution dicts to merge into target.sensor_contributions.

        Parameters
        ----------
        target : object with .x, .y, .type, .is_emitting
        uavs   : iterable of UAVs with .id, .x, .y
        """
        out: list[dict] = []
        now = time.time()
        for cfg in self.streams:
            if cfg.requires_emitter and not getattr(target, "is_emitting", False):
                continue
            if cfg.daytime_only and not self.is_daytime:
                continue
            # Confidence degrades with weather
            conf = cfg.base_confidence * (1.0 - cfg.weather_sensitivity * self.weather_factor)
            # Pick a UAV to attribute it to (closest one within range)
            attrib = self._pick_uav(target, uavs, cfg.range_max_km)
            if attrib is None:
                continue
            uav_id, range_m, bearing = attrib
            # Add some noise so confidence doesn't look canned
            noisy_conf = max(0.0, min(1.0, conf + self.rng.gauss(0.0, 0.04)))
            kind = self.rng.choice(cfg.source_kinds) if cfg.source_kinds else cfg.sensor_type
            out.append({
                "uav_id": uav_id,
                "sensor_type": cfg.sensor_type,
                "confidence": round(noisy_conf, 4),
                "range_m": round(range_m, 1),
                "bearing_deg": round(bearing, 1),
                "timestamp": now,
                "source_kind": kind,
            })
        return out

    def _pick_uav(
        self,
        target,
        uavs: Iterable,
        range_max_km: float,
    ) -> Optional[tuple[int, float, float]]:
        """Return (uav_id, range_m, bearing_deg) for the closest UAV within range, else None."""
        best = None
        best_range_m = float("inf")
        for u in uavs:
            dx_deg = u.x - target.x
            dy_deg = u.y - target.y
            # Approximate flat-earth distance (1 deg ≈ 111 km)
            range_m = math.hypot(dx_deg, dy_deg) * 111_000.0
            if range_m > range_max_km * 1000.0:
                continue
            if range_m < best_range_m:
                best = u
                best_range_m = range_m
        if best is None:
            return None
        bearing = math.degrees(math.atan2(best.x - target.x, best.y - target.y)) % 360.0
        return (best.id, best_range_m, bearing)


def attach_to_target(target, uavs: Iterable, simulator: MultiIntSimulator) -> int:
    """Append synthesised multi-INT contributions to target.sensor_contributions.

    Returns number of new contributions appended. Idempotent within a tick — won't
    re-add a sensor_type that's already present this frame because sensor_fusion
    already deduplicates on (uav_id, sensor_type) by max confidence.
    """
    extra = simulator.extra_contributions(target, uavs)
    if not extra:
        return 0
    if not hasattr(target, "sensor_contributions") or target.sensor_contributions is None:
        target.sensor_contributions = []
    target.sensor_contributions.extend(extra)
    return len(extra)
