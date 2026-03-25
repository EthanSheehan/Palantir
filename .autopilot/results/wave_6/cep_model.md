# W6-012: CEP Engagement Model

**Status:** COMPLETE
**Date:** 2026-03-25

## Files Created

- `src/python/cep_model.py` — CEP engagement model (147 lines)
- `src/python/tests/test_cep_model.py` — 37 tests (all passing)

## Implementation Summary

### WeaponType enum
Four precision munitions: `HELLFIRE`, `JDAM`, `SDB`, `JAVELIN`

### WEAPON_PROFILES
Each weapon: `(cep_meters, lethal_radius_meters, max_range_km)`
- HELLFIRE: 1.5m CEP, 8m lethal radius, 8km range
- JDAM: 5.0m CEP, 20m lethal radius, 28km range
- SDB: 3.0m CEP, 12m lethal radius, 110km glide range
- JAVELIN: 0.5m CEP, 5m lethal radius, 4.5km range

### TARGET_HARDNESS
All 10 target types: SAM(0.6), TEL(0.5), TRUCK(0.1), CP(0.4), MANPADS(0.1),
RADAR(0.3), C2_NODE(0.5), LOGISTICS(0.1), ARTILLERY(0.7), APC(0.8)

### sample_miss_distance(cep, seed)
Rayleigh distribution via Box-Muller. sigma = cep/sqrt(ln(4)) ensures
P(r <= CEP) = 0.5 (correct CEP definition). ~50% of samples fall within CEP.

### compute_damage(miss_distance, lethal_radius, target_hardness)
`exp(-(miss/lr)^2) * (1 - hardness * 0.5)`
Continuous exponential decay. Returns [0.0, 1.0].

### simulate_engagement(weapon, target_type, seed) -> EngagementResult
Frozen dataclass: miss_distance, damage, is_kill (damage > 0.5), weapon, target_type.
Deterministic when seed is provided.

### estimate_pk(weapon, target_type, n_samples) -> float
Monte Carlo Pk via sequential seeds. Default 1000 samples.

## Test Results

```
37 passed in 0.66s
```

## Full Suite

```
1589 passed, 68 warnings (1 pre-existing failure in test_enemy_uavs.py unrelated)
```

## Acceptance Criteria Met

- [x] Gaussian/Rayleigh miss-distance model: sample from Rayleigh with sigma derived from CEP
- [x] Lethal radius per target type and weapon type: WEAPON_PROFILES + TARGET_HARDNESS
- [x] Damage as continuous function of miss distance: exponential decay formula
- [x] stdlib only (math, random) — no numpy
- [x] Immutable patterns (frozen dataclasses)
- [x] Functions < 50 lines, file < 800 lines
