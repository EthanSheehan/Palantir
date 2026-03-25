# Wave 6A Code Review

**Reviewed modules:** forward_sim, delta_compression, vectorized_detection, comms_sim, cep_model, dbscan_clustering
**Reviewer:** Sonnet 4.6
**Date:** 2026-03-25

---

## Summary Table

| Module | File Lines | Immutability | Functions >50 Lines | Error Handling | Tests | Overall |
|--------|-----------|-------------|---------------------|----------------|-------|---------|
| forward_sim.py | 158 | PASS | None | PASS | Good | MEDIUM issues |
| delta_compression.py | 204 | PASS | None | PASS | Excellent | LOW issues |
| vectorized_detection.py | 243 | PASS | None | PASS | Excellent | MEDIUM issues |
| comms_sim.py | 144 | PASS | None | PASS | Excellent | LOW issues |
| cep_model.py | 161 | PASS | None | PASS | Excellent | LOW issues |
| dbscan_clustering.py | 236 | Partial FAIL | None | PASS | Excellent | MEDIUM issues |

---

## CRITICAL Issues

None found.

---

## HIGH Issues

### H1 — forward_sim.py: `evaluate_coas` evaluates all COAs with the same unmodified model

**File:** `src/python/forward_sim.py:135-145`

Each COA in `evaluate_coas` is evaluated by running `project_forward(model, ticks)` on the **base model** — no COA-specific setup is applied to the clone before ticking. The function signature accepts `coas: list[dict]` but ignores the COA's content entirely when projecting. Every candidate receives an identical score because every clone starts from the same state with no COA-specific modifications applied.

```python
# Current (line 136) — all COAs get the same score
score = await asyncio.to_thread(project_forward, model, ticks)
```

The COA dict (containing fields like `type`, `effector_name`, `pk_estimate`) is never passed into the projection. This means the ranking is meaningless — a comparator function that always returns equal values.

**Impact:** Breaks the primary purpose of the module. Decision-support scores are all equal; the ranking is arbitrary (sort order of gather results).

**Fix:** Either apply COA-specific pre-tick mutations to the clone before simulation, or document that this is a placeholder awaiting a `apply_coa(clone, coa)` integration point. At minimum, the test `test_returns_sorted_by_projected_score_descending` only passes because the test patches `project_forward` to return mock scores — it does not validate real COA differentiation.

---

### H2 — forward_sim.py: `_evaluate_single` runs projection twice for no benefit

**File:** `src/python/forward_sim.py:135-142`

Inside `_evaluate_single`, the simulation is projected twice — once for the score (`project_forward`) and once for the summary (`_project_and_summarise`). Both functions independently clone the model and tick forward. This doubles CPU and memory cost with no benefit; the summary data should be extracted from the same clone used for scoring.

**Impact:** 2x CPU cost per COA in the hot evaluation loop.

**Fix:** Merge into a single `_project_and_score` helper that returns `(score, summary)` from one clone.

---

## MEDIUM Issues

### M1 — dbscan_clustering.py: `_expand_cluster` mutates `labels` list in-place

**File:** `src/python/dbscan_clustering.py:65-90`

`_expand_cluster` directly mutates the `labels` list passed in. This is an internal implementation detail of the DBSCAN algorithm (mutation within `run_dbscan`), but it violates the project's immutability rule. The `labels` list is allocated inside `run_dbscan` and never escapes, so there is no external side effect, but the pattern is inconsistent with the codebase convention.

**Severity note:** Not a correctness bug, but flagged as a convention violation per coding-style.md (ALWAYS create new objects, NEVER mutate).

**Fix:** Acceptable to document with a comment: `# labels is a local scratch buffer — intentional internal mutation`. Alternatively, refactor to a recursive functional approach (less practical for DBSCAN).

---

### M2 — dbscan_clustering.py: `_list_has_ids` heuristic only checks `lst[0]`

**File:** `src/python/delta_compression.py:85-86`

`_list_has_ids` only inspects the first element to decide whether the list uses ID-based diffing. A heterogeneous list where the first item lacks an `id` but others have it would be treated as non-ID-keyed, losing the efficiency of per-item diffing. More critically, a list where only some items have `id` will silently fall back to wholesale replacement.

**Fix:** Check that all (or majority) of items have `id`, or document the constraint that ID-keyed lists must have `id` on every element.

---

### M3 — vectorized_detection.py: imports private symbol `_FALLBACK_RCS_M2` from sensor_model

**File:** `src/python/vectorized_detection.py:20-25`

The import includes `_FALLBACK_RCS_M2` and `RCS_TABLE` — `_FALLBACK_RCS_M2` starts with `_`, marking it as a private/internal symbol of `sensor_model`. Importing private symbols creates a brittle coupling; if `sensor_model` refactors its internals, `vectorized_detection` silently breaks.

**Fix:** Either expose `FALLBACK_RCS_M2` as a public constant in `sensor_model`, or define a local fallback in `vectorized_detection` for clarity.

---

### M4 — forward_sim.py: `project_forward` swallows tick errors silently after first exception

**File:** `src/python/forward_sim.py:108-112`

On tick error, `project_forward` logs a warning and `break`s — returning the score at whatever intermediate tick count it reached. This means a model that raises on tick 3 of 50 returns a completely different (and probably lower) score than a model that ticks all 50. Callers cannot distinguish a completed projection from a partial one.

**Fix:** Either re-raise, or return a `ProjectionResult` dataclass with a `completed: bool` field and the final score, so callers can discard partial projections.

---

### M5 — comms_sim.py: `attempt_delivery` uses module-level `random.random()` — not seeded

**File:** `src/python/comms_sim.py:124`

`attempt_delivery` calls `random.random()` from the module-level `random` instance, which is not seeded. This makes simulation results non-reproducible. The `cep_model` module correctly accepts an optional `seed` parameter; `comms_sim` should do the same.

**Fix:** Accept an optional `rng: random.Random | None = None` parameter, defaulting to `random.random()` when not provided. This matches the pattern used in `cep_model.sample_miss_distance`.

---

### M6 — dbscan_clustering.py: `match_clusters` uses O(N²) linear search

**File:** `src/python/dbscan_clustering.py:178-195`

The matching loop iterates over all `available_prev` for each new cluster. For K clusters, this is O(K²). In the current use case (low cluster counts at sim scale) this is not a performance problem, but it is worth noting for future scaling. No immediate fix required; document the quadratic complexity with a comment.

---

## LOW Issues

### L1 — forward_sim.py: `score_state` double-counts some states

**File:** `src/python/forward_sim.py:68-75`

The score for `CLASSIFIED`, `TRACKED`, `LOCKED`, `NOMINATED` is `_WEIGHT_VERIFIED * 0.6`. The `_ACTIVE_THREAT_STATES` constant defined at line 34 lists `TRACKED`, `LOCKED`, `NOMINATED` but they are not actually penalised in `score_state` (no deduction for unresolved high-confidence threats). The comment at line 61 says "active high-confidence threats remaining (unresolved)" but no such penalty is in the implementation.

**Fix:** Align comments with implementation or implement the missing threat penalty.

---

### L2 — delta_compression.py: `apply_delta` does a shallow `dict.copy` for base

**File:** `src/python/delta_compression.py:95`

`apply_delta` creates `result = dict(base_state)` (shallow copy), then recurses into nested dicts via `apply_delta(base_val, val)`. Nested dicts that are not touched by the delta are not copied — they remain as references to the original `base_state` values. An external mutation of `base_state`'s nested structure after `apply_delta` would corrupt the returned result.

This is a narrow concern (callers rarely hold both the result and the original simultaneously), but it is inconsistent with the immutability contract.

**Fix:** Use `copy.deepcopy(base_state)` as the starting point, or document that nested non-delta'd values are shared references.

---

### L3 — comms_sim.py: `CommsState.links` typed as `dict` not `dict[str, CommsLink]`

**File:** `src/python/comms_sim.py:58`

The `links` field is annotated as `dict` rather than `dict[str, CommsLink]`. This loses type safety; callers cannot rely on type checkers to catch incorrect link usage.

**Fix:** Annotate as `dict[str, CommsLink]` or use `from __future__ import annotations` + `dict[str, "CommsLink"]`.

---

### L4 — vectorized_detection.py: benchmark function included in production module

**File:** `src/python/vectorized_detection.py:181-243`

`benchmark_scalar_vs_vectorized` is a development/perf utility function included in the production module. It references `time` and imports `math`, neither of which are needed by the public API. This adds ~60 lines of non-production code to a module that should be focused on detection logic.

**Recommendation:** Move to `src/python/benchmarks/benchmark_vectorized_detection.py` or a test file.

---

### L5 — cep_model.py: `KILL_THRESHOLD` is module-level but not in `__all__` or public API doc

**File:** `src/python/cep_model.py:65`

`KILL_THRESHOLD = 0.5` is a tunable constant that affects all kill/no-kill decisions system-wide. It is not documented in the module docstring's public API section, which only lists functions. If an operator or integration test adjusts the threshold, behaviour changes globally.

**Recommendation:** Add to the module docstring's public API section, or make it a parameter of `simulate_engagement`.

---

### L6 — dbscan_clustering.py: noise label sentinel `0` collides with "no cluster assigned"

**File:** `src/python/dbscan_clustering.py:122`

```python
labels[i] = 0  # noise marker (0 = noise in our scheme)
```

The initialisation at line 114 sets `labels = [-1] * n` with `-1 = unvisited`. Noise is then set to `0`. But `cluster_label` starts at `0` and is incremented to `1` before the first real cluster is assigned (line 124: `cluster_label += 1`). This means cluster labels start at `1`, so `0` is effectively unused as a real cluster ID. The noise sentinel `0` does not collide in practice, but it is confusing: standard DBSCAN uses `-1` for noise. The deviation from convention requires a clear comment.

**Fix:** Use `-1` for noise consistently (standard DBSCAN convention) or add a clear inline comment explaining the scheme.

---

## Test Quality Assessment

| File | Test Count | Coverage | Quality |
|------|-----------|----------|---------|
| test_forward_sim.py | 15 | High | Good — integration test with `SimulationModel` is strong |
| test_delta_compression.py | 25 | Very High | Excellent — roundtrip test is particularly valuable |
| test_vectorized_detection.py | 18 | Very High | Excellent — `test_matches_scalar_compute_pd` bulk equivalence test is best in class |
| test_comms_sim.py | 40+ | Very High | Excellent — comprehensive state-machine coverage |
| test_cep_model.py | 22 | Very High | Excellent — statistical test `test_rayleigh_distribution_median` validates physics |
| test_dbscan_clustering.py | 25 | High | Good — covers edge cases and persistence ID lifecycle |

**Notable test issues:**

- `test_forward_sim.py:208-238` — `test_returns_sorted_by_projected_score_descending` patches `project_forward` to return mock scores. It does not test real COA differentiation. This test would pass even with the H1 bug.
- `test_cep_model.py:297-302` — `test_hard_target_lower_pk_than_soft` has a weak assertion (`or pk_sam <= pk_truck + 0.2`) that will pass even if Pk ordering is reversed. Strengthen the assertion.
- `test_comms_sim.py:332-344` / `test_comms_sim.py:346-358` — `test_contested_eventually_delivers` and `test_contested_sometimes_drops` are probabilistic and could rarely flake. Low risk at current sample sizes (30 trials, 30% and 90% loss), but worth noting.

---

## Action Items (Priority Order)

1. **[HIGH]** Fix `evaluate_coas` to apply COA-specific state before projection, or document the placeholder limitation — `forward_sim.py`
2. **[HIGH]** Merge double-projection in `_evaluate_single` into single projection — `forward_sim.py`
3. **[MEDIUM]** Document or refactor `_expand_cluster` in-place mutation — `dbscan_clustering.py`
4. **[MEDIUM]** Fix `_list_has_ids` to check all items, not just `lst[0]` — `delta_compression.py`
5. **[MEDIUM]** Expose `_FALLBACK_RCS_M2` as public in `sensor_model` — `vectorized_detection.py`
6. **[MEDIUM]** Add `rng` seed parameter to `attempt_delivery` — `comms_sim.py`
7. **[LOW]** Align `score_state` comments with implementation — `forward_sim.py`
8. **[LOW]** Fix `apply_delta` shallow copy for nested dicts — `delta_compression.py`
9. **[LOW]** Add type annotation `dict[str, CommsLink]` to `CommsState.links` — `comms_sim.py`
10. **[LOW]** Move benchmark function out of production module — `vectorized_detection.py`
