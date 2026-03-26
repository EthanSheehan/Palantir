# Wave 6 Fixes: sensor_weighting.py + lost_link.py

## Status: COMPLETE — 90/90 tests pass

---

## sensor_weighting.py

### MEDIUM — `time_of_day` NaN propagation (line ~160)
**Fix:** Added validation at `compute_sensor_fitness()` entry:
```python
if not math.isfinite(time_of_day) or not (0.0 <= time_of_day < 24.0):
    raise ValueError(f"time_of_day must be in [0, 24); got {time_of_day!r}")
```

### MEDIUM — `weather["intensity"]` NaN bypass (lines ~60, ~93)
**Fix:** Added NaN guard + clamp in both `_eo_ir_weather_weight` and `_sar_weather_weight`:
```python
intensity = float(weather.get("intensity", 0.0))
if not math.isfinite(intensity):
    intensity = 0.0
intensity = max(0.0, min(1.0, intensity))
```

### MEDIUM — Unknown sensor type silent fallback (line ~172)
**Fix:** Added `import logging` and warning log in the else branch:
```python
logging.warning("Unknown sensor type %r — using neutral fitness 0.5", sensor_type)
```

### MEDIUM — `weight_fusion_contributions` hardcoded "TRUCK" (line ~211)
**Fix:** Added `target_type: str = "TRUCK"` parameter to `weight_fusion_contributions` signature. Passed to `compute_sensor_fitness` instead of hardcoded literal.

---

## lost_link.py

### MEDIUM — Negative `current_tick` disables failsafe (line ~140)
**Fix:** Clamped ticks_since to non-negative:
```python
ticks_since = max(0, current_tick - existing.last_contact_tick)
```

### LOW — `timeout_ticks=0` always fires failsafe
**Fix:** Added validation in `configure_drone()` before constructing `LinkConfig`:
```python
if timeout_ticks < 1:
    raise ValueError(f"timeout_ticks must be >= 1; got {timeout_ticks}")
```

### LOW — Type annotations for `LinkState`
**Fix:** Changed generic `dict` to typed variants:
```python
configs: dict[str, LinkConfig]
statuses: dict[str, LinkStatus]
```

### LOW — SAFE_LAND comment
**Fix:** Added inline comment on the `SAFE_LAND` entry in `_BEHAVIOR_MODE_MAP`:
```python
LostLinkBehavior.SAFE_LAND: "RTB",  # SAFE_LAND: sim has no dedicated land-in-place mode; RTB is the safest available behavior
```

---

## Test Results

```
90 passed in 17.47s
  - test_sensor_weighting.py: 30 passed
  - test_lost_link.py: 60 passed
```
