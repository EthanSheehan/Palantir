from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import structlog
import yaml

logger = structlog.get_logger(__name__)

THEATERS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "theaters"


# ---------------------------------------------------------------------------
# Immutable config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Bounds:
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float


@dataclass(frozen=True)
class GridConfig:
    cols: int
    rows: int


@dataclass(frozen=True)
class UAVConfig:
    count: int
    type: str
    base_lon: float
    base_lat: float
    default_altitude_m: int
    sensor_type: str
    endurance_hours: int


@dataclass(frozen=True)
class LauncherConfig:
    name: str
    lat: float
    lon: float
    capacity: int = 4


@dataclass(frozen=True)
class BlueForce:
    uavs: UAVConfig
    launchers: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class RedUnit:
    type: str
    count: int
    behavior: str
    speed_kmh: Optional[int] = None
    threat_range_km: Optional[int] = None
    detection_range_km: Optional[int] = None


@dataclass(frozen=True)
class RedForce:
    units: Tuple[RedUnit, ...]


@dataclass(frozen=True)
class Environment:
    weather: str
    time_of_day: str
    terrain: str


@dataclass(frozen=True)
class EnemyUAVUnitConfig:
    behavior: str
    count: int
    speed_kmh: float = 400.0


@dataclass(frozen=True)
class EnemyUAVConfig:
    units: Tuple[EnemyUAVUnitConfig, ...]


@dataclass(frozen=True)
class TheaterConfig:
    name: str
    description: str
    bounds: Bounds
    grid: GridConfig
    blue_force: BlueForce
    red_force: RedForce
    environment: Environment
    enemy_uavs: Optional[EnemyUAVConfig] = None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class TheaterValidationError(ValueError):
    """Raised when a theater configuration is invalid."""


def _require_key(data: dict, key: str, context: str) -> object:
    if key not in data:
        raise TheaterValidationError(f"Missing required key '{key}' in {context}")
    return data[key]


def _validate_bounds(bounds: Bounds) -> None:
    if bounds.min_lon >= bounds.max_lon:
        raise TheaterValidationError(f"Bounds min_lon ({bounds.min_lon}) must be less than max_lon ({bounds.max_lon})")
    if bounds.min_lat >= bounds.max_lat:
        raise TheaterValidationError(f"Bounds min_lat ({bounds.min_lat}) must be less than max_lat ({bounds.max_lat})")


def _validate_positive(value: int, field: str, context: str) -> None:
    if value <= 0:
        raise TheaterValidationError(f"{field} must be positive in {context}, got {value}")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_bounds(raw: dict) -> Bounds:
    return Bounds(
        min_lon=float(_require_key(raw, "min_lon", "bounds")),
        max_lon=float(_require_key(raw, "max_lon", "bounds")),
        min_lat=float(_require_key(raw, "min_lat", "bounds")),
        max_lat=float(_require_key(raw, "max_lat", "bounds")),
    )


def _parse_grid(raw: dict) -> GridConfig:
    return GridConfig(
        cols=int(_require_key(raw, "cols", "grid")),
        rows=int(_require_key(raw, "rows", "grid")),
    )


def _parse_uav(raw: dict) -> UAVConfig:
    return UAVConfig(
        count=int(_require_key(raw, "count", "blue_force.uavs")),
        type=str(_require_key(raw, "type", "blue_force.uavs")),
        base_lon=float(_require_key(raw, "base_lon", "blue_force.uavs")),
        base_lat=float(_require_key(raw, "base_lat", "blue_force.uavs")),
        default_altitude_m=int(_require_key(raw, "default_altitude_m", "blue_force.uavs")),
        sensor_type=str(_require_key(raw, "sensor_type", "blue_force.uavs")),
        endurance_hours=int(_require_key(raw, "endurance_hours", "blue_force.uavs")),
    )


def _parse_red_unit(raw: dict, index: int) -> RedUnit:
    ctx = f"red_force.units[{index}]"
    return RedUnit(
        type=str(_require_key(raw, "type", ctx)),
        count=int(_require_key(raw, "count", ctx)),
        behavior=str(_require_key(raw, "behavior", ctx)),
        speed_kmh=int(raw["speed_kmh"]) if "speed_kmh" in raw else None,
        threat_range_km=int(raw["threat_range_km"]) if "threat_range_km" in raw else None,
        detection_range_km=int(raw["detection_range_km"]) if "detection_range_km" in raw else None,
    )


def _parse_red_force(raw: dict) -> RedForce:
    raw_units = _require_key(raw, "units", "red_force")
    if not isinstance(raw_units, list) or len(raw_units) == 0:
        raise TheaterValidationError("red_force.units must be a non-empty list")
    units = tuple(_parse_red_unit(u, i) for i, u in enumerate(raw_units))
    return RedForce(units=units)


def _parse_enemy_uav_unit(raw: dict, index: int) -> EnemyUAVUnitConfig:
    ctx = f"enemy_uavs[{index}]"
    return EnemyUAVUnitConfig(
        behavior=str(_require_key(raw, "behavior", ctx)),
        count=int(_require_key(raw, "count", ctx)),
        speed_kmh=float(raw.get("speed_kmh", 400.0)),
    )


def _parse_enemy_uavs(raw: list) -> EnemyUAVConfig:
    units = tuple(_parse_enemy_uav_unit(u, i) for i, u in enumerate(raw))
    return EnemyUAVConfig(units=units)


def _parse_environment(raw: dict) -> Environment:
    return Environment(
        weather=str(_require_key(raw, "weather", "environment")),
        time_of_day=str(_require_key(raw, "time_of_day", "environment")),
        terrain=str(_require_key(raw, "terrain", "environment")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_theater(theater_name: str) -> TheaterConfig:
    """Load theater from YAML file in theaters/ directory.

    Raises TheaterValidationError for invalid or missing configs.
    Raises FileNotFoundError if the theater file does not exist.
    """
    yaml_path = THEATERS_DIR / f"{theater_name}.yaml"
    if not yaml_path.exists():
        available = list_theaters()
        raise FileNotFoundError(f"Theater '{theater_name}' not found at {yaml_path}. Available theaters: {available}")

    logger.info("loading_theater", theater=theater_name, path=str(yaml_path))

    with open(yaml_path, "r") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise TheaterValidationError(f"Theater file must contain a YAML mapping, got {type(data).__name__}")

    bounds = _parse_bounds(dict(_require_key(data, "bounds", "root")))
    _validate_bounds(bounds)

    grid = _parse_grid(dict(_require_key(data, "grid", "root")))
    _validate_positive(grid.cols, "cols", "grid")
    _validate_positive(grid.rows, "rows", "grid")

    blue_raw = dict(_require_key(data, "blue_force", "root"))
    uav_config = _parse_uav(dict(_require_key(blue_raw, "uavs", "blue_force")))
    _validate_positive(uav_config.count, "count", "blue_force.uavs")
    blue_force = BlueForce(uavs=uav_config)

    red_force = _parse_red_force(dict(_require_key(data, "red_force", "root")))
    for unit in red_force.units:
        _validate_positive(unit.count, "count", f"red_force.units ({unit.type})")

    environment = _parse_environment(dict(_require_key(data, "environment", "root")))

    enemy_uavs_cfg: Optional[EnemyUAVConfig] = None
    if "enemy_uavs" in data and isinstance(data["enemy_uavs"], list):
        enemy_uavs_cfg = _parse_enemy_uavs(data["enemy_uavs"])

    config = TheaterConfig(
        name=str(_require_key(data, "name", "root")),
        description=str(_require_key(data, "description", "root")),
        bounds=bounds,
        grid=grid,
        blue_force=blue_force,
        red_force=red_force,
        environment=environment,
        enemy_uavs=enemy_uavs_cfg,
    )

    logger.info(
        "theater_loaded",
        theater=config.name,
        uav_count=config.blue_force.uavs.count,
        red_unit_types=len(config.red_force.units),
    )
    return config


def list_theaters() -> List[str]:
    """List available theater names from the theaters/ directory."""
    if not THEATERS_DIR.is_dir():
        return []
    return sorted(p.stem for p in THEATERS_DIR.glob("*.yaml"))
