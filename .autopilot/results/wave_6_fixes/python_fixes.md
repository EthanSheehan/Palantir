# Wave 6C-Alpha Python Review Fixes

## Changes Made

### Security H-1: `/metrics` endpoint localhost restriction
**File:** `src/python/api_main.py`
**Status:** Already implemented — endpoint already checks `request.client.host` against `("127.0.0.1", "::1", "localhost", "testclient")` before the fix request was submitted. No change needed.

### Security M-5: Clamp autonomy_level in `update_gauges()`
**File:** `src/python/metrics.py` (line ~101)
**Change:** Added whitelist check — `autonomy_level if autonomy_level in ("MANUAL", "SUPERVISED", "AUTONOMOUS") else "MANUAL"`. Prevents arbitrary strings from reaching the metrics output.

### Python M-001: Counter HELP/TYPE lines missing `_total` suffix
**File:** `src/python/metrics.py` (lines ~149-152)
**Change:** Rewrote `_counter()` helper to compute `full_name = f"{name}_total"` and use it consistently for all three lines (HELP, TYPE, value). Previously HELP/TYPE used `name` but the metric line used `name_total` — violating the Prometheus format spec.

### Python M-002: Histogram `le="0.1"` bucket always equalled `+Inf`
**File:** `src/python/metrics.py` (lines ~154-162)
**Change:** Removed the misleading `le="0.1"` bucket. Now only emits the required `le="+Inf"` bucket plus `_count` and `_sum`. Reordered to `bucket → count → sum` (conventional Prometheus order).

### Security M-6: Warn when `auth_enabled=True` with default `demo_token`
**File:** `src/python/config.py` (after `_validate_ssl`)
**Change:** Added `_validate_demo_token` model_validator that emits a `UserWarning` if `auth_enabled=True` and `demo_token == "dev"`. Helps catch misconfigured production deployments.

### Security M-2: SSL file existence validation
**File:** `src/python/config.py`
**Status:** Already implemented — `_validate_ssl` already calls `os.path.isfile()` for both cert and key paths. No change needed.

### Python L-002: CORS origins hardcoded
**File:** `src/python/api_main.py` (line ~286)
**Change:** Changed `allow_origins=["http://localhost:3000"]` to `allow_origins=settings.allowed_origins`. Origins now driven by the `ALLOWED_ORIGINS` env var (defaulting to `["http://localhost:3000", "http://localhost:8000"]`).

### Test update: `test_generate_metrics_text_has_help_lines`
**File:** `src/python/tests/test_metrics.py` (line 197)
**Change:** Updated assertion from `"# HELP grid_sentinel_detection_events"` to `"# HELP grid_sentinel_detection_events_total"` to match the corrected M-001 output.

## Test Results

```
collected 47 items

src/python/tests/test_metrics.py .............................  [61%]
src/python/tests/test_tls_config.py ..................       [100%]

47 passed in 5.95s
```

All 47 tests pass with no failures or warnings.
