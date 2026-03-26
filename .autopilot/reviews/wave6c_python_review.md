# Wave 6C-Alpha Python Review

**Reviewer:** Python Reviewer (Sonnet 4.6)
**Date:** 2026-03-26
**Scope:** `metrics.py`, `tests/test_metrics.py`, `config.py` (TLS additions), `api_main.py` (/metrics endpoint + TLS + origin validation), `tests/test_tls_config.py`

---

## Summary

Overall quality is HIGH. The implementation is clean, well-structured, and follows project conventions. Two MEDIUM issues and several LOW issues are noted. No CRITICALs or HIGHs found.

---

## MEDIUM Issues

### M-001: `_counter` helper emits wrong metric name suffix in Prometheus format

**File:** `src/python/metrics.py:149-152`

```python
def _counter(name: str, help_text: str, value: float) -> None:
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} counter")
    lines.append(f"{name}_total {_fmt(value)}")   # ← appends _total to value line
```

The `# HELP` and `# TYPE` lines use `name` (e.g., `palantir_detection_events`), but the value line emits `{name}_total`. Per Prometheus exposition format 0.0.4, the `# HELP` and `# TYPE` lines must use the **same metric family name** as the sample lines. When name already ends with the base name, Prometheus scrapers expect `# HELP palantir_detection_events_total …` and `# TYPE palantir_detection_events_total counter` — not a mismatch between declaration and sample.

The test at line 197 (`test_generate_metrics_text_has_help_lines`) checks for `"# HELP palantir_detection_events"` which passes, but a real Prometheus scraper would log a parse warning about the `_total` sample having no matching TYPE declaration.

**Fix:** Either pass the `_total` suffixed name into the helper, or have the helper use `f"{name}_total"` consistently for both HELP/TYPE and value lines.

```python
def _counter(name: str, help_text: str, value: float) -> None:
    full_name = f"{name}_total"
    lines.append(f"# HELP {full_name} {help_text}")
    lines.append(f"# TYPE {full_name} counter")
    lines.append(f"{full_name} {_fmt(value)}")
```

---

### M-002: `_histogram` helper includes a misleading/incorrect bucket

**File:** `src/python/metrics.py:154-161`

```python
def _histogram(name, help_text, count, total, p50):
    ...
    lines.append(f'{name}_bucket{{le="0.1"}} {count}')   # ← always equal to total count
    lines.append(f'{name}_bucket{{le="+Inf"}} {count}')
```

The `le="0.1"` bucket always emits `count` (total tick count), implying ALL ticks finished in ≤0.1s. This is semantically wrong when ticks exceed 100ms (which happens under load). A Prometheus histogram with a single incorrect cumulative bucket misleads dashboards — any alerting rule based on `le="0.1"` percentile will report 100% under 100ms even during overload.

**Fix options:**
1. Remove the `le="0.1"` bucket entirely and only emit `+Inf` (valid minimal histogram).
2. Track actual bucket counts during `record_tick` (store `fast_count` for ticks < 0.1s).
3. Document explicitly that it is a placeholder and not reliable (least preferred).

---

## LOW Issues

### L-001: `_percentile` computed but not used in output

**File:** `src/python/metrics.py:223-227` and `155`

`_percentile` is called to populate `MetricsSnapshot.tick_duration_p50` (line 111), and `get_snapshot()` computes it, but `generate_metrics_text()` passes `p50` to `_histogram` which never uses the `p50` parameter (the parameter is accepted but ignored). The unused computation and the dead parameter are harmless but confusing.

**Fix:** Either use `p50` in the histogram output (e.g., emit it as a summary quantile), or remove the `p50` parameter from `_histogram` to clarify intent.

---

### L-002: `CORS allow_origins` does not consume `settings.allowed_origins`

**File:** `src/python/api_main.py:284-290`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # ← hardcoded, ignores settings.allowed_origins
    ...
)
```

`settings.allowed_origins` is used for WebSocket origin checking via `_is_origin_allowed()`, but the HTTP CORS middleware still uses a hardcoded list. This creates a split-brain: an operator who adds `https://ops-dashboard.example.com` to `ALLOWED_ORIGINS` env var will have WebSocket connections permitted but preflight CORS requests rejected. This is a consistency issue rather than a security hole (WebSocket origin check is the critical path), but it will confuse deployments.

**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    ...
)
```

---

### L-003: TLS keyfile not validated for existence at startup

**File:** `src/python/config.py:148-155`

The `_validate_ssl` validator confirms `ssl_certfile` and `ssl_keyfile` are non-None strings when `ssl_enabled=True`, but does not verify the paths actually exist on disk. If a path is misconfigured, the failure will happen late (when uvicorn tries to load the cert) rather than at startup with a clear error.

**Fix (optional):** Add path existence checks:
```python
from pathlib import Path
if not Path(self.ssl_certfile).exists():
    raise ValueError(f"ssl_certfile not found: {self.ssl_certfile}")
if not Path(self.ssl_keyfile).exists():
    raise ValueError(f"ssl_keyfile not found: {self.ssl_keyfile}")
```
Note: This is a startup-time improvement, not a security issue — uvicorn will fail safely either way.

---

### L-004: WebSocket origin check happens after `websocket.close()` on rejected connection

**File:** `src/python/api_main.py:518-522`

```python
origin = websocket.headers.get("origin")
if not _is_origin_allowed(origin):
    await websocket.close(code=4003, reason="Origin not allowed")
    ...
```

`websocket.close()` is called without a prior `websocket.accept()`. In the Starlette/FastAPI WebSocket lifecycle, calling `close()` before `accept()` sends the HTTP 403/reject at the HTTP upgrade level (which is correct), but the behavior depends on the ASGI transport. The existing pattern is consistent with the connection-limit check at line 512-516, so this is low risk. Documenting the intent would reduce future confusion.

---

### L-005: Module-level import order inconsistency

**File:** `src/python/api_main.py:57-58`

```python
import metrics as _metrics
from fastapi.responses import PlainTextResponse
```

These two imports appear after the large block of project-local imports (lines 23-56). PEP 8 / isort convention puts stdlib imports first, then third-party (fastapi), then local. The `PlainTextResponse` import belongs with the other `fastapi` imports at lines 36-37. Low cosmetic impact but inconsistent with the rest of the file.

---

### L-006: Test helper `_make_settings` uses `AUTH_DISABLED` env var that doesn't exist in config

**File:** `src/python/tests/test_tls_config.py:21`

```python
clean_env = {
    "AUTH_DISABLED": "true",   # ← no such field in PalantirSettings
}
```

`PalantirSettings` has `auth_enabled` (default `False`), not `AUTH_DISABLED`. This environment variable has no effect; the test is relying on `auth_enabled`'s default of `False` rather than explicitly disabling auth. Not a bug (tests pass correctly), but the comment/intent is misleading.

**Fix:** Remove `AUTH_DISABLED` or replace with `"AUTH_ENABLED": "false"`.

---

### L-007: `test_tls_config.py` duplicates `_is_origin_allowed` logic instead of importing it

**File:** `src/python/tests/test_tls_config.py:95-134`

The `_get_origin_checker` helper re-implements the `_is_origin_allowed` function inline rather than importing and testing it directly. The comment acknowledges this is because `api_main` has module-level side effects. This is a valid workaround, but it means the tests don't actually test the real production function — if `_is_origin_allowed` in `api_main.py` diverges from the test copy, tests will pass while the production code is broken.

**Preferred fix:** Extract `_is_origin_allowed` into a separate utility module (e.g., `origin_check.py`) with no side effects, then import and test it directly. This also makes it easier to reuse in future WebSocket endpoints.

---

## Positive Observations

- **Thread safety:** `metrics.py` correctly uses a single `threading.Lock` protecting all state mutations. The `get_snapshot()` function releases the lock before returning (lock is scoped to just the copy operation), which is correct.
- **Immutability:** `MetricsSnapshot` uses `frozen=True` dataclass — fully immutable as required by project conventions.
- **Bounded memory:** `record_tick` trims the window at 10,000 entries (keeps last 5,000) — prevents unbounded growth.
- **`reset()` is safe:** Uses `global _state` with lock to swap the entire state object atomically.
- **Origin checking logic is correct:** IPv6 bracket notation handled, path components stripped, all scheme prefixes covered.
- **Config validator is proper:** `model_validator(mode="after")` correctly fires after all fields are populated.
- **Test coverage is thorough:** 29 metrics tests + 18 TLS tests cover happy path, edge cases, and integration. `autouse=True` reset fixture ensures test isolation.
- **`/metrics` endpoint:** Correct `PlainTextResponse` with proper `text/plain; version=0.0.4; charset=utf-8` content-type — scraper-compatible.

---

## Issue Summary

| ID | Severity | File | Description |
|----|----------|------|-------------|
| M-001 | MEDIUM | metrics.py:149 | Counter HELP/TYPE lines don't include `_total` suffix — Prometheus parse warning |
| M-002 | MEDIUM | metrics.py:158 | `le="0.1"` histogram bucket always equals total count — semantically wrong |
| L-001 | LOW | metrics.py:155 | `p50` parameter computed but unused in histogram output |
| L-002 | LOW | api_main.py:286 | CORS middleware uses hardcoded origins instead of `settings.allowed_origins` |
| L-003 | LOW | config.py:148 | TLS cert/key paths not validated for existence at startup |
| L-004 | LOW | api_main.py:518 | `websocket.close()` before `accept()` — intent not documented |
| L-005 | LOW | api_main.py:57 | Import order inconsistency (cosmetic) |
| L-006 | LOW | test_tls_config.py:21 | `AUTH_DISABLED` env var doesn't exist in `PalantirSettings` |
| L-007 | LOW | test_tls_config.py:95 | Test duplicates production logic instead of importing it |

**CRITICAL:** 0
**HIGH:** 0
**MEDIUM:** 2
**LOW:** 7
