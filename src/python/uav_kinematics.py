"""
uav_kinematics.py
=================
3-DOF point-mass UAV kinematics for the AMC-Grid C2 system.

Provides immutable state types and pure functions for:
- Wind vector ground-speed / track-angle adjustment
- Rate-limited kinematic time-stepping (heading, altitude, speed)
- Minimum-separation collision detection
- Collision avoidance heading offset
- Proportional navigation guidance law

All types are frozen dataclasses. No state is mutated anywhere.
Uses only the standard library `math` module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Metres per degree of latitude (approximate, equirectangular)
_LAT_M_PER_DEG = 111_320.0

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KinematicState:
    """Immutable 3-DOF point-mass state for a single UAV."""

    lat: float  # Decimal degrees
    lon: float  # Decimal degrees
    alt_m: float  # Altitude above sea level, metres
    speed_mps: float  # Airspeed, metres per second
    heading_deg: float  # True heading, degrees (0 = north, clockwise)
    climb_rate_mps: float  # Vertical speed, m/s (positive = climbing)


@dataclass(frozen=True)
class WindVector:
    """Immutable wind vector.

    direction_deg follows meteorological convention: the direction *from*
    which the wind blows (0° = wind from north, 90° = wind from east).
    """

    speed_mps: float  # Wind speed, m/s
    direction_deg: float  # Direction wind is coming FROM, degrees


@dataclass(frozen=True)
class UAVConstraints:
    """Immutable flight-envelope limits for a UAV type."""

    max_speed_mps: float  # Maximum airspeed, m/s
    min_speed_mps: float  # Minimum airspeed (stall margin), m/s
    max_turn_rate_dps: float  # Maximum bank turn rate, degrees/second
    max_climb_rate_mps: float  # Maximum climb/descent rate, m/s
    min_altitude_m: float  # Minimum safe altitude, m AGL (treated as ASL here)
    max_altitude_m: float  # Service ceiling, m
    min_separation_m: float  # Minimum safe separation between UAVs, m


# MQ-9 Reaper class defaults
DEFAULT_CONSTRAINTS = UAVConstraints(
    max_speed_mps=110.0,  # ~215 knots TAS
    min_speed_mps=55.0,  # ~107 knots (stall margin)
    max_turn_rate_dps=3.0,  # Standard rate turn for fixed-wing ISR
    max_climb_rate_mps=15.0,  # ~3000 ft/min
    min_altitude_m=300.0,  # Safe operating floor
    max_altitude_m=15_000.0,  # ~50,000 ft service ceiling
    min_separation_m=500.0,  # Safety bubble radius
)


# Maximum number of positions accepted by check_separation to prevent O(n²) blowup
_MAX_POSITIONS = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _horiz_dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular horizontal distance in metres."""
    mid_lat_rad = math.radians((lat1 + lat2) / 2.0)
    lon_m_per_deg = _LAT_M_PER_DEG * math.cos(mid_lat_rad)
    dy = (lat2 - lat1) * _LAT_M_PER_DEG
    dx = (lon2 - lon1) * lon_m_per_deg
    return math.hypot(dy, dx)


def _normalize_heading(deg: float) -> float:
    """Wrap heading into [0, 360)."""
    return deg % 360.0


def _heading_delta(current: float, target: float) -> float:
    """Signed shortest angular difference from current to target heading, degrees."""
    diff = (target - current + 180.0) % 360.0 - 180.0
    return diff


def _validate_state(state: KinematicState) -> None:
    """Raise ValueError if any critical state field is non-finite."""
    fields = {
        "lat": state.lat,
        "lon": state.lon,
        "alt_m": state.alt_m,
        "speed_mps": state.speed_mps,
        "heading_deg": state.heading_deg,
    }
    for name, value in fields.items():
        if not math.isfinite(value):
            raise ValueError(f"KinematicState.{name} is non-finite: {value}")


def _update_heading(
    state: KinematicState,
    target_heading: float,
    dt: float,
    constraints: UAVConstraints,
) -> float:
    """Return rate-limited new heading."""
    delta = _heading_delta(state.heading_deg, target_heading)
    max_delta = constraints.max_turn_rate_dps * dt
    clamped_delta = max(min(delta, max_delta), -max_delta)
    return _normalize_heading(state.heading_deg + clamped_delta)


def _update_altitude(
    state: KinematicState,
    target_alt: float,
    dt: float,
    constraints: UAVConstraints,
) -> tuple[float, float]:
    """Return (new_alt_m, new_climb_rate_mps) after rate-limited altitude change."""
    alt_error = target_alt - state.alt_m
    max_alt_change = constraints.max_climb_rate_mps * dt
    clamped_alt_change = max(min(alt_error, max_alt_change), -max_alt_change)
    new_alt = state.alt_m + clamped_alt_change
    new_alt = max(constraints.min_altitude_m, min(constraints.max_altitude_m, new_alt))
    new_climb_rate = clamped_alt_change / dt
    return new_alt, new_climb_rate


def _update_position(
    lat: float,
    lon: float,
    speed: float,
    heading: float,
    dt: float,
    wind: Optional[WindVector],
) -> tuple[float, float]:
    """Return (new_lat, new_lon) after advancing position by dt seconds."""
    if wind is not None:
        tmp = KinematicState(
            lat=lat, lon=lon, alt_m=0.0, speed_mps=speed, heading_deg=heading, climb_rate_mps=0.0
        )
        ground_speed, track_deg = apply_wind(tmp, wind)
    else:
        ground_speed = speed
        track_deg = heading

    track_rad = math.radians(track_deg)
    mid_lat_rad = math.radians(lat)
    lon_m_per_deg = _LAT_M_PER_DEG * math.cos(mid_lat_rad)

    d_north_m = ground_speed * math.cos(track_rad) * dt
    d_east_m = ground_speed * math.sin(track_rad) * dt

    new_lat = lat + d_north_m / _LAT_M_PER_DEG
    new_lon = lon + d_east_m / (lon_m_per_deg if lon_m_per_deg > 1e-9 else 1.0)
    return new_lat, new_lon


# ---------------------------------------------------------------------------
# Wind correction
# ---------------------------------------------------------------------------


def apply_wind(state: KinematicState, wind: WindVector) -> tuple[float, float]:
    """Compute ground speed and track angle given airspeed, heading, and wind.

    Wind direction convention: wind FROM that direction (meteorological).
    The wind *velocity vector* (the direction the wind travels *toward*) is
    therefore 180° from direction_deg.

    Returns
    -------
    (ground_speed_mps, track_deg) — both floats.
    """
    if wind.speed_mps < 1e-9:
        return (float(state.speed_mps), float(_normalize_heading(state.heading_deg)))

    # Airspeed vector (where the UAV points)
    heading_rad = math.radians(state.heading_deg)
    air_vx = state.speed_mps * math.sin(heading_rad)  # east component
    air_vy = state.speed_mps * math.cos(heading_rad)  # north component

    # Wind velocity vector: wind travels TOWARD (direction_deg + 180)
    wind_toward_rad = math.radians(wind.direction_deg + 180.0)
    wind_vx = wind.speed_mps * math.sin(wind_toward_rad)
    wind_vy = wind.speed_mps * math.cos(wind_toward_rad)

    # Ground velocity = air velocity + wind velocity
    gnd_vx = air_vx + wind_vx
    gnd_vy = air_vy + wind_vy

    ground_speed = math.hypot(gnd_vx, gnd_vy)

    # Track angle: atan2(east, north) — same convention as heading
    if ground_speed < 1e-9:
        track_deg = _normalize_heading(state.heading_deg)
    else:
        track_deg = _normalize_heading(math.degrees(math.atan2(gnd_vx, gnd_vy)))

    return (float(ground_speed), float(track_deg))


# ---------------------------------------------------------------------------
# Kinematic time-step
# ---------------------------------------------------------------------------


def step_kinematics(
    state: KinematicState,
    target_heading: float,
    target_alt: float,
    target_speed: float,
    dt: float,
    constraints: UAVConstraints,
    wind: Optional[WindVector],
) -> KinematicState:
    """Advance kinematic state by dt seconds toward commanded values.

    All changes are rate-limited by UAVConstraints. Returns a new
    KinematicState (input is never modified).

    Parameters
    ----------
    state          : Current kinematic state.
    target_heading : Commanded heading, degrees.
    target_alt     : Commanded altitude, metres.
    target_speed   : Commanded airspeed, m/s.
    dt             : Time step, seconds.
    constraints    : UAV flight-envelope limits.
    wind           : Optional wind vector (None = calm).
    """
    if dt <= 0.0:
        raise ValueError(f"dt must be positive; got {dt}")
    _validate_state(state)

    new_heading = _update_heading(state, target_heading, dt, constraints)
    new_speed = max(constraints.min_speed_mps, min(constraints.max_speed_mps, target_speed))
    new_alt, new_climb_rate = _update_altitude(state, target_alt, dt, constraints)
    new_lat, new_lon = _update_position(state.lat, state.lon, new_speed, new_heading, dt, wind)

    return KinematicState(
        lat=new_lat,
        lon=new_lon,
        alt_m=new_alt,
        speed_mps=new_speed,
        heading_deg=new_heading,
        climb_rate_mps=new_climb_rate,
    )


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------


def check_separation(
    positions: list[KinematicState],
    min_sep_m: float,
) -> list[tuple[int, int]]:
    """Return all (i, j) pairs where horizontal separation < min_sep_m.

    Only returns pairs where i < j. Altitude is ignored (horizontal only).
    """
    n = len(positions)
    if n > _MAX_POSITIONS:
        raise ValueError(f"check_separation: positions length {n} exceeds _MAX_POSITIONS={_MAX_POSITIONS}")

    for state in positions:
        _validate_state(state)

    violations: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            dist = _horiz_dist_m(
                positions[i].lat,
                positions[i].lon,
                positions[j].lat,
                positions[j].lon,
            )
            if dist < min_sep_m:
                violations.append((i, j))
    return violations


# ---------------------------------------------------------------------------
# Collision avoidance
# ---------------------------------------------------------------------------


def avoid_collision(
    state: KinematicState,
    threats: list[KinematicState],
    min_sep_m: float,
) -> float:
    """Return a heading offset in degrees to avoid nearby threats.

    For each threat within min_sep_m, computes a repulsion bearing (away
    from the threat) weighted by proximity. Returns the net heading offset
    to add to the current commanded heading. Returns 0.0 when no threats
    are within range.

    The offset is clamped to [-90, 90] degrees.
    """
    if not threats:
        return 0.0

    total_offset = 0.0
    any_threat = False

    for threat in threats:
        dist = _horiz_dist_m(state.lat, state.lon, threat.lat, threat.lon)
        if dist >= min_sep_m:
            continue

        any_threat = True

        # Bearing FROM threat TO self (repulsion direction)
        d_lat = state.lat - threat.lat
        d_lon = state.lon - threat.lon
        mid_lat_rad = math.radians((state.lat + threat.lat) / 2.0)
        lon_scale = math.cos(mid_lat_rad)

        if abs(d_lat) < 1e-9 and abs(d_lon) < 1e-9:
            # Collocated: escape perpendicular to current heading (turn right)
            bearing_deg = _normalize_heading(state.heading_deg + 90.0)
        else:
            bearing_rad = math.atan2(d_lon * lon_scale, d_lat)
            bearing_deg = math.degrees(bearing_rad)

        # Heading delta needed to face away from threat
        delta = _heading_delta(state.heading_deg, bearing_deg)

        # Weight by proximity (closer = stronger)
        if min_sep_m > 1e-9:
            weight = 1.0 - (dist / min_sep_m)
        else:
            weight = 1.0

        total_offset += delta * weight

    if not any_threat:
        return 0.0

    # Clamp to ±90°
    return float(max(min(total_offset, 90.0), -90.0))


# ---------------------------------------------------------------------------
# Proportional navigation
# ---------------------------------------------------------------------------


def proportional_navigation(
    pursuer: KinematicState,
    target_lat: float,
    target_lon: float,
    target_speed: float,
    target_heading: float,
    nav_gain: float = 3.0,
) -> float:
    """Proportional navigation guidance law.

    Computes the commanded heading for a pursuer using the PN law:
        a_cmd = N * V_c * omega_los

    where omega_los is the line-of-sight (LOS) rotation rate and N is the
    navigation gain.

    Since we operate in discrete degrees/ticks rather than acceleration,
    we return the desired heading directly (pursuer heading + PN correction).

    Parameters
    ----------
    pursuer        : Current pursuer kinematic state.
    target_lat/lon : Target position, decimal degrees.
    target_speed   : Target speed, m/s.
    target_heading : Target heading, degrees.
    nav_gain       : Navigation constant N (typically 3–5).

    Returns
    -------
    Commanded heading in degrees [0, 360).
    """
    if nav_gain <= 0:
        raise ValueError(f"nav_gain must be positive; got {nav_gain}")
    _validate_state(pursuer)

    # Current LOS bearing (pursuer → target)
    d_lat = target_lat - pursuer.lat
    d_lon = target_lon - pursuer.lon
    mid_lat_rad = math.radians((pursuer.lat + target_lat) / 2.0)
    lon_scale = math.cos(mid_lat_rad)

    los_dist_m = _horiz_dist_m(pursuer.lat, pursuer.lon, target_lat, target_lon)

    if los_dist_m < 1e-3:
        # Already at target — maintain current heading
        return float(_normalize_heading(pursuer.heading_deg))

    los_bearing = math.degrees(math.atan2(d_lon * lon_scale, d_lat))

    # Target velocity components (m/s, in north/east frame)
    t_hdg_rad = math.radians(target_heading)
    t_vx = target_speed * math.sin(t_hdg_rad)  # east
    t_vy = target_speed * math.cos(t_hdg_rad)  # north

    # Pursuer velocity components
    p_hdg_rad = math.radians(pursuer.heading_deg)
    p_vx = pursuer.speed_mps * math.sin(p_hdg_rad)
    p_vy = pursuer.speed_mps * math.cos(p_hdg_rad)

    # Closing velocity (relative velocity projected onto LOS)
    rel_vx = p_vx - t_vx
    rel_vy = p_vy - t_vy

    los_rad = math.radians(los_bearing)
    los_nx = math.sin(los_rad)  # unit LOS east
    los_ny = math.cos(los_rad)  # unit LOS north

    closing_speed = rel_vx * los_nx + rel_vy * los_ny

    # LOS rate (omega = perpendicular relative velocity / range)
    perp_vx = rel_vx - closing_speed * los_nx
    perp_vy = rel_vy - closing_speed * los_ny
    perp_speed = math.hypot(perp_vx, perp_vy)

    # Sign of LOS rotation (cross >= 0 means CCW rotation → positive omega_los)
    cross = los_nx * perp_vy - los_ny * perp_vx
    omega_los = (perp_speed / los_dist_m) if cross >= 0 else (-perp_speed / los_dist_m)

    # PN commanded lateral acceleration (m/s²) — repurposed as heading rate (deg/s)
    # Use closing speed magnitude; fall back to pursuer speed if closing_speed ~ 0
    vc = abs(closing_speed) if abs(closing_speed) > 1.0 else pursuer.speed_mps
    a_cmd_dps = nav_gain * vc * math.degrees(omega_los) / max(pursuer.speed_mps, 1.0)

    # Commanded heading = LOS bearing + PN correction
    cmd_heading = _normalize_heading(los_bearing + a_cmd_dps)

    return float(cmd_heading)
