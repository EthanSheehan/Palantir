"""
cep_model.py
============
CEP (Circular Error Probable) engagement outcome model.

Replaces binary hit/miss with a physics-based Rayleigh miss-distance distribution.
Damage is a continuous function of miss distance, lethal radius, and target hardness.

Uses only stdlib (math, random) — no numpy dependency.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class WeaponType(str, Enum):
    HELLFIRE = "HELLFIRE"
    JDAM = "JDAM"
    SDB = "SDB"
    JAVELIN = "JAVELIN"


# ---------------------------------------------------------------------------
# Weapon profiles: weapon_type -> (cep_meters, lethal_radius_meters, max_range_km)
# ---------------------------------------------------------------------------

WEAPON_PROFILES: dict[WeaponType, tuple[float, float, float]] = {
    WeaponType.HELLFIRE: (1.5, 8.0, 8.0),  # AGM-114: ~1.5m CEP, ~8m lethal radius
    WeaponType.JDAM: (5.0, 20.0, 28.0),  # GBU-38: ~5m CEP, large blast radius
    WeaponType.SDB: (3.0, 12.0, 110.0),  # GBU-39: ~3m CEP, 110km glide range
    WeaponType.JAVELIN: (0.5, 5.0, 4.5),  # FGM-148: <0.5m CEP, ~4.5km max range
}


# ---------------------------------------------------------------------------
# Target hardness: target_type -> hardness_factor (0.0 = soft, 1.0 = hardened)
# ---------------------------------------------------------------------------

TARGET_HARDNESS: dict[str, float] = {
    "SAM": 0.6,  # Vehicle-mounted, moderate armor
    "TEL": 0.5,  # Transporter erector launcher, moderate armor
    "TRUCK": 0.1,  # Soft-skinned vehicle
    "CP": 0.4,  # Command post, some protection
    "MANPADS": 0.1,  # Shoulder-launched, soft target
    "RADAR": 0.3,  # Radar array, semi-hardened
    "C2_NODE": 0.5,  # Command node, moderate hardening
    "LOGISTICS": 0.1,  # Supply trucks, soft targets
    "ARTILLERY": 0.7,  # Hardened artillery piece
    "APC": 0.8,  # Armored Personnel Carrier, well-armored
}

# Default hardness for unknown target types
_DEFAULT_HARDNESS = 0.3

# Kill threshold: damage above this value counts as a kill
KILL_THRESHOLD = 0.5

# Validate weapon profiles at module load to catch bad config early
for _weapon, (_cep, _lethal_radius, _max_range) in WEAPON_PROFILES.items():
    if _lethal_radius <= 0:
        raise ValueError(f"WEAPON_PROFILES[{_weapon}]: lethal_radius must be > 0, got {_lethal_radius}")


# ---------------------------------------------------------------------------
# Immutable result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngagementResult:
    miss_distance: float  # meters from aim point
    damage: float  # 0.0 (miss) to 1.0 (destroyed)
    is_kill: bool  # damage > KILL_THRESHOLD
    weapon: WeaponType
    target_type: str


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def sample_miss_distance(cep: float, seed: Optional[int] = None) -> float:
    """Sample miss distance (meters) from Rayleigh distribution with the given CEP.

    Rayleigh distribution is the correct model for 2D miss distance.
    sigma = cep / sqrt(ln(4)) so that median of Rayleigh equals CEP.
    """
    rng = random.Random(seed)
    # Rayleigh sigma from CEP definition: P(r <= CEP) = 0.5
    # For Rayleigh: P(r <= x) = 1 - exp(-x^2 / (2*sigma^2))
    # Setting to 0.5: sigma = cep / sqrt(2 * ln(2)) = cep / sqrt(ln(4))
    sigma = cep / math.sqrt(math.log(4.0))

    # Sample Rayleigh via Box-Muller: sqrt(x^2 + y^2) where x,y ~ N(0, sigma)
    x = rng.gauss(0.0, sigma)
    y = rng.gauss(0.0, sigma)
    return math.hypot(x, y)


def compute_damage(miss_distance: float, lethal_radius: float, target_hardness: float) -> float:
    """Compute damage as a continuous function of miss distance.

    Formula: exp(-(miss_distance / lethal_radius)^2) * (1 - target_hardness * 0.5)

    Returns a value in [0.0, 1.0].
    """
    blast_decay = math.exp(-((miss_distance / lethal_radius) ** 2))
    hardness_factor = 1.0 - target_hardness * 0.5
    return blast_decay * hardness_factor


def simulate_engagement(
    weapon: WeaponType,
    target_type: str,
    seed: Optional[int] = None,
) -> EngagementResult:
    """Simulate a single engagement and return an immutable EngagementResult.

    Samples miss distance from Rayleigh(CEP), computes damage via exponential
    decay formula, and determines kill based on damage threshold.
    """
    cep, lethal_radius, _ = WEAPON_PROFILES[weapon]
    hardness = TARGET_HARDNESS.get(target_type, _DEFAULT_HARDNESS)

    miss_distance = sample_miss_distance(cep=cep, seed=seed)
    damage = compute_damage(
        miss_distance=miss_distance,
        lethal_radius=lethal_radius,
        target_hardness=hardness,
    )
    is_kill = damage > KILL_THRESHOLD

    return EngagementResult(
        miss_distance=miss_distance,
        damage=damage,
        is_kill=is_kill,
        weapon=weapon,
        target_type=target_type,
    )


def estimate_pk(
    weapon: WeaponType,
    target_type: str,
    n_samples: int = 1000,
    seed: Optional[int] = None,
) -> float:
    """Monte Carlo estimate of probability of kill (Pk).

    Runs n_samples engagements using independent random draws and returns
    the fraction that result in is_kill == True.

    seed: explicit integer seed for reproducibility; defaults to None (cryptographically
    random via os.urandom) for true Monte Carlo behavior.
    """
    if seed is None:
        seed = int.from_bytes(os.urandom(4), "big")
    rng = random.Random(seed)
    cep, lethal_radius, _ = WEAPON_PROFILES[weapon]
    hardness = TARGET_HARDNESS.get(target_type, _DEFAULT_HARDNESS)
    sigma = cep / math.sqrt(math.log(4.0))

    kills = 0
    for _ in range(n_samples):
        x = rng.gauss(0.0, sigma)
        y = rng.gauss(0.0, sigma)
        miss_distance = math.hypot(x, y)
        damage = compute_damage(
            miss_distance=miss_distance,
            lethal_radius=lethal_radius,
            target_hardness=hardness,
        )
        if damage > KILL_THRESHOLD:
            kills += 1
    return kills / n_samples
