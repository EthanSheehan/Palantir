# Wave 6A Security Review

Reviewed: 2026-03-25
Modules: forward_sim.py, delta_compression.py, vectorized_detection.py, comms_sim.py, cep_model.py, dbscan_clustering.py

---

## Summary Table

| Module | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| forward_sim.py | 0 | 1 | 2 | 1 |
| delta_compression.py | 0 | 1 | 1 | 1 |
| vectorized_detection.py | 0 | 0 | 2 | 1 |
| comms_sim.py | 0 | 0 | 1 | 1 |
| cep_model.py | 0 | 1 | 1 | 0 |
| dbscan_clustering.py | 0 | 0 | 2 | 1 |

**Total: 0 CRITICAL, 3 HIGH, 9 MEDIUM, 5 LOW**

---

## forward_sim.py

### HIGH — Unbounded COA list causes unbounded parallelism (resource exhaustion)
**Location:** `evaluate_coas()`, line 144
```python
evaluated = await asyncio.gather(*[_evaluate_single(coa) for coa in coas])
```
`asyncio.gather` spawns one `to_thread` task per COA with no cap. Each task calls `clone_simulation` (deepcopy of the full sim model) and runs up to 50 ticks. An attacker or buggy caller sending 1000 COAs would exhaust the thread pool and memory simultaneously.

**Fix:** Add a semaphore or batch limit:
```python
_MAX_PARALLEL_COAS = 8
sem = asyncio.Semaphore(_MAX_PARALLEL_COAS)
async def _evaluate_single(coa):
    async with sem:
        ...
```
Also enforce a hard cap: `if len(coas) > 64: raise ValueError(...)`.

---

### MEDIUM — `ticks` parameter is unconstrained
**Location:** `project_forward()` and `evaluate_coas()`, lines 100, 116
```python
def project_forward(model: Any, ticks: int = 50) -> float:
```
If a caller passes `ticks=10_000_000`, each simulation clone runs millions of ticks. There is no upper bound. Combined with the parallelism issue above, this compounds the resource exhaustion risk.

**Fix:** Clamp at entry: `ticks = min(ticks, 500)` or raise on excessive values.

---

### MEDIUM — Global recursion limit mutation is not thread-safe
**Location:** `clone_simulation()`, lines 44–50
```python
old_limit = sys.getrecursionlimit()
sys.setrecursionlimit(_DEEPCOPY_RECURSION_LIMIT)
...
sys.setrecursionlimit(old_limit)
```
`sys.setrecursionlimit` is a global interpreter setting. If multiple threads call `clone_simulation` concurrently (as they do via `asyncio.to_thread`), one thread can restore the old limit while another is mid-deepcopy at elevated depth, causing `RecursionError` in the other thread. This is a TOCTOU race on a global setting.

**Fix:** Use a threading lock, or restructure the model to avoid circular references that require recursion depth > 1000.

---

### LOW — Score function silently handles NaN/inf from external model state
**Location:** `score_state()` / `_summarise_state()`, lines 53–97
`getattr(uav, "fuel_hours", _FUEL_FULL_HOURS)` accepts whatever value the model returns. If `fuel_hours` is `NaN` or negative, `fuel_ratio = min(1.0, NaN / 6.0)` propagates NaN silently into the score. The `max(0.0, total)` at line 82 does not guard against NaN (NaN comparisons always return False).

**Fix:** Sanitize: `fuel = max(0.0, float(fuel_hours))` with an explicit NaN guard before use.

---

## delta_compression.py

### HIGH — Deeply nested payloads cause unbounded recursion (stack overflow)
**Location:** `compute_delta()` / `apply_delta()`, lines 16, 89
Both functions call themselves recursively on nested dicts with no depth limit. A crafted payload like `{"a": {"a": {"a": ...}}}` at depth 1000+ will hit Python's default recursion limit and crash the WebSocket handler with an unhandled `RecursionError`.

This input arrives from the WebSocket tick loop — any state dict that happens to be deeply nested (or is injected by a client) can trigger this.

**Fix:** Add a depth parameter and raise a controlled error at a safe limit (e.g., 50):
```python
def compute_delta(prev_state, curr_state, _depth=0):
    if _depth > 50:
        raise ValueError("State nesting too deep for delta computation")
```

---

### MEDIUM — `__deleted__` sentinel collides with legitimate state keys
**Location:** Lines 13, 80, 129
```python
_DELETED = "__deleted__"
```
If a legitimate state dict happens to contain a key whose value is the string `"__deleted__"`, `apply_delta` will incorrectly delete that key rather than preserving the value. The sentinel is a plain string with no namespace protection.

**Fix:** Use a unique typed sentinel object: `_DELETED = object()` and serialize/deserialize it with a private prefix that no real key value could match (e.g., `"\x00DELETED\x00"`).

---

### LOW — No size bound on `DeltaTracker._states`
**Location:** `DeltaTracker`, line 165
The tracker stores a deep copy of the full state per client indefinitely. If `remove_client()` is never called (connection leak, crash before cleanup), state accumulates unbounded. At 10 Hz ticks with large state dicts, this is a slow memory leak.

**Fix:** Add a max-clients cap and/or an LRU eviction policy.

---

## vectorized_detection.py

### MEDIUM — `sensor_type` key is not validated before dict lookup
**Location:** `vectorized_detection_probability()`, line 108
```python
sensor_cfg = SENSOR_CONFIGS[sensor_type]
```
`SENSOR_CONFIGS` is a dict with three known keys. An invalid `sensor_type` raises an unhandled `KeyError` which propagates up through the 10 Hz simulation loop. This could crash the simulation tick if a caller passes an unknown sensor string.

**Fix:** Validate at function entry:
```python
if sensor_type not in SENSOR_CONFIGS:
    raise ValueError(f"Unknown sensor_type {sensor_type!r}. Valid: {list(SENSOR_CONFIGS)}")
```

---

### MEDIUM — Missing guards for empty or all-NaN distance/RCS arrays
**Location:** `detect_all()` and `vectorized_detection_probability()`, lines 137, 86
If `positions_to_array` returns arrays with NaN values (e.g., entity dicts with `lat=None` or `lat=float('nan')`), the distance computation propagates NaN silently. `np.where(pd_matrix >= threshold)` with NaN values in the matrix produces no matches — incorrect silent behaviour rather than a detectable error.

**Fix:** Validate input arrays for NaN/inf after construction:
```python
if not np.isfinite(uav_pos).all() or not np.isfinite(tgt_pos).all():
    raise ValueError("Entity positions contain NaN or inf values")
```

---

### LOW — Benchmark uses hardcoded lat/lon ranges (Romania theater)
**Location:** `benchmark_scalar_vs_vectorized()`, lines 193–196
The benchmark is embedded in the module and runs if `__name__ == "__main__"`. This is a cosmetic/maintenance issue rather than a security concern, but it imports internal sensor model symbols (`_FALLBACK_RCS_M2`) that are private API. Not a security risk in isolation.

---

## comms_sim.py

### MEDIUM — `degrade_all_links()` accepts `factor=0` causing division by zero
**Location:** `degrade_all_links()`, line 103
```python
new_bw = max(0.0, link.bandwidth_kbps / factor)
```
If `factor=0` is passed (e.g., total EW denial), this raises `ZeroDivisionError`. The function has no input validation. Since `factor` is meant to represent a degradation multiplier, zero is a plausible EW scenario value.

**Fix:** Guard at function entry: `if factor <= 0: raise ValueError("factor must be > 0")` or clamp: `factor = max(factor, 1e-9)`.

---

### LOW — `random.random()` in `attempt_delivery()` uses the global random state
**Location:** `attempt_delivery()`, line 124
```python
random.random() < link.packet_loss_rate
```
The module-level `import random` uses Python's global `random.Random` instance, which is shared across all threads. This is not a security vulnerability (the comms sim is purely internal), but it means delivery outcomes can't be seeded deterministically for replay/testing without affecting all other code using `random`. Consistent with `cep_model.py` pattern below.

---

## cep_model.py

### HIGH — Predictable sequential seeds in Monte Carlo make Pk estimates deterministic and gameable
**Location:** `estimate_pk()`, lines 147–160
```python
kills = sum(
    1 for i in range(n_samples) if simulate_engagement(..., seed=i).is_kill
)
```
Seeds 0, 1, 2, ... are used sequentially. `random.Random(seed)` produces the same Rayleigh sample every run. The Pk estimate is therefore fully deterministic across process restarts. This is by design for reproducibility but means an adversary who knows the weapon/target type can predict exactly which engagements will result in kills by iterating seeds offline.

More critically for simulation integrity: if the AAR engine or scenario scripting relies on `estimate_pk()` to generate outcome distributions, the distribution is frozen — the same 1000 seeds always produce the same fraction. This is not true Monte Carlo.

**Fix:** Use unseeded `random.Random()` for Monte Carlo (no seed), or use a single cryptographically random seed per simulation run rather than sequential integers.

---

### MEDIUM — `lethal_radius` of 0 causes ZeroDivisionError in `compute_damage()`
**Location:** `compute_damage()`, line 112
```python
blast_decay = math.exp(-((miss_distance / lethal_radius) ** 2))
```
If a future weapon profile is added with `lethal_radius=0`, this raises `ZeroDivisionError`. There is no validation of weapon profile values at load time.

**Fix:** Validate `WEAPON_PROFILES` at module load: assert all `lethal_radius > 0`. Or guard in `compute_damage`: `if lethal_radius <= 0: return 0.0`.

---

## dbscan_clustering.py

### MEDIUM — `run_dbscan()` is O(n²) with no input size limit
**Location:** `run_dbscan()`, line 93; `_neighbors()`, line 59
The scratch DBSCAN implementation calls `_neighbors()` for every point, and each `_neighbors()` call iterates all `n` points. Worst-case is O(n²) haversine computations. With no cap on `len(targets)`, a caller passing 10,000 targets would execute 100 million haversine calls synchronously on the simulation tick thread.

**Fix:** Add an input guard:
```python
MAX_TARGETS = 500
if len(detected) > MAX_TARGETS:
    detected = detected[:MAX_TARGETS]  # or sample, or raise
```

---

### MEDIUM — `targets` list items are trusted without key validation
**Location:** `run_dbscan()`, lines 108–112
```python
detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
points = [(t["lat"], t["lon"]) for t in detected]
```
`t["lat"]` and `t["lon"]` are direct dict key accesses with no validation. If a target dict is missing `lat`/`lon` (e.g., a partially initialized object), this raises `KeyError`. If values are non-numeric, the haversine computation will raise `TypeError`. The filter only checks `state` — no schema validation.

**Fix:** Validate coordinates at extraction:
```python
points = []
for t in detected:
    try:
        lat, lon = float(t["lat"]), float(t["lon"])
    except (KeyError, TypeError, ValueError):
        continue  # skip malformed targets
    points.append((lat, lon))
```

---

### LOW — `match_clusters()` uses string prefix parsing for ID management
**Location:** `match_clusters()`, lines 163–168
```python
num = int(c.cluster_id.replace("CLU-", ""))
```
Cluster IDs are parsed by stripping a prefix string. If a cluster ID was assigned externally or via a scenario script with a different format, the `int()` conversion silently falls through the `except (ValueError, AttributeError)` handler, which is correct but fragile. Not a security concern in the current code path, but coupling ID format to string parsing is brittle.

---

## Priority Fix Order

1. **HIGH — forward_sim unbounded COA parallelism**: Add semaphore + list cap before next load test
2. **HIGH — delta_compression unbounded recursion**: Add depth guard before WebSocket goes to prod
3. **HIGH — cep_model sequential seeds**: Replace with per-run random seed for valid Monte Carlo
4. **MEDIUM — forward_sim ticks unconstrained**: Clamp to reasonable max
5. **MEDIUM — forward_sim recursion limit race**: Add threading.Lock or restructure
6. **MEDIUM — delta_compression __deleted__ sentinel collision**: Replace with sentinel object
7. **MEDIUM — vectorized_detection missing sensor_type validation**: Add KeyError guard
8. **MEDIUM — vectorized_detection NaN propagation**: Validate arrays after construction
9. **MEDIUM — comms_sim degrade_all_links factor=0**: Guard against zero division
10. **MEDIUM — cep_model lethal_radius=0**: Validate WEAPON_PROFILES at load time
11. **MEDIUM — dbscan O(n²) no size limit**: Cap input to MAX_TARGETS
12. **MEDIUM — dbscan missing lat/lon validation**: Wrap in try/except at extraction
