# Wave 5 Security Review

**Scope:** `git diff ad9b42c..HEAD` — Waves 5A and 5B
**Files reviewed:** `rbac.py`, `llm_sanitizer.py`, `scenario_engine.py`, `checkpoint.py`, `websocket_handlers.py` (new handlers), `report_generator.py`, `hitl_manager.py`, `sim_controller.py`, `weather_engine.py`, `uav_logistics.py`, `terrain_model.py`, `jammer_model.py`, `scenarios/demo.yaml`

---

## CRITICAL

### CRIT-01 — RBAC module is not wired into any WebSocket or HTTP handler

**File:** `src/python/rbac.py`, `src/python/websocket_handlers.py`, `src/python/api_main.py`

`rbac.py` defines `validate_token()` and `check_permission()` but neither function is imported or called anywhere in `websocket_handlers.py` or `api_main.py`. The PERMISSION_MATRIX that restricts `authorize_coa`, `approve_nomination`, `reset`, `SET_SCENARIO`, etc. to COMMANDER/ADMIN roles is entirely dead code.

**Impact:** Any unauthenticated WebSocket client can send `authorize_coa`, `reset`, or `SET_SCENARIO` without restriction. The RBAC module provides false assurance — it exists but enforces nothing.

**Fix:** Import `check_permission` in `websocket_handlers.py` and call it inside `handle_payload()` before dispatching to handlers. Pass the authenticated role from the WebSocket session context.

---

### CRIT-02 — `AUTH_DISABLED` defaults to `true` in `rbac.py`

**File:** `src/python/rbac.py`, line 25

```python
AUTH_DISABLED: bool = os.environ.get("AUTH_DISABLED", "true").lower() in ("true", "1", "yes")
```

The existing `src/python/auth.py` defaults `AUTH_DISABLED` to `"false"`. The new `rbac.py` defaults it to `"true"`. This inconsistency means that even when `rbac.py` is wired in (CRIT-01 fixed), it will silently run in fully-open ADMIN mode in any deployment that does not explicitly set `AUTH_DISABLED=false`.

**Impact:** Production deployments missing the env var get full admin access for all clients, with no warning.

**Fix:** Change default to `"false"` to match `auth.py`. If dev convenience requires it, document the env var prominently and emit a startup warning when `AUTH_DISABLED=true` is active.

---

## HIGH

### HIGH-01 — Hardcoded JWT fallback secret

**File:** `src/python/rbac.py`, line 26

```python
JWT_SECRET: str = os.environ.get("JWT_SECRET", "palantir-dev-secret")
```

`"palantir-dev-secret"` is now committed to git history. If `JWT_SECRET` is not set in production, all tokens are signed with a publicly known secret, allowing any attacker to forge valid JWTs for any role including ADMIN.

**Impact:** Complete authentication bypass when `JWT_SECRET` env var is absent.

**Fix:** Remove the fallback. Raise `RuntimeError` at import time if `AUTH_DISABLED` is false and `JWT_SECRET` is not set or is shorter than 32 characters.

---

### HIGH-02 — `set_roe` WebSocket action accepts arbitrary file paths (path traversal)

**File:** `src/python/websocket_handlers.py`, lines 715–735

```python
path = payload.get("path")
# No path validation — passes directly to ROEEngine.load_from_yaml(path)
new_engine = ROEEngine.load_from_yaml(path)
```

A WebSocket client (currently any client, given CRIT-01) can supply `path = "../../../etc/passwd"` or any absolute path on the server. `ROEEngine.load_from_yaml()` opens the file directly with no allowlist or base-directory restriction. The `yaml.safe_load` call in `roe_engine.py` prevents code execution but still leaks arbitrary file content if the YAML parse fails with an error message, and allows loading unintended ROE configurations.

**Impact:** Arbitrary file read (via error messages), unintended ROE reconfiguration.

**Fix:** Resolve the path and assert it is within an allowed directory (e.g., the `roe/` folder relative to the project root) before passing to `load_from_yaml`.

```python
import pathlib
ROE_BASE = pathlib.Path("roe").resolve()
resolved = pathlib.Path(path).resolve()
if not str(resolved).startswith(str(ROE_BASE)):
    await _send_error(websocket, "Invalid ROE path", "set_roe")
    return
```

---

### HIGH-03 — `llm_sanitizer.py` has no input length limit

**File:** `src/python/llm_sanitizer.py`, `sanitize_prompt_input()`

The function normalizes and scans arbitrarily long strings. There is no maximum length cap. A client can send a multi-megabyte string, causing expensive regex scanning across all 10 compiled patterns on each call.

**Impact:** Denial of service via CPU exhaustion on the sanitizer hot path (called before every LLM prompt).

**Fix:** Add a length cap early in `sanitize_prompt_input()`:

```python
MAX_PROMPT_INPUT = 4096
if len(text) > MAX_PROMPT_INPUT:
    raise InjectionDetected(f"Input exceeds maximum length of {MAX_PROMPT_INPUT}")
```

---

### HIGH-04 — `checkpoint.py` `load_from_file` accepts unconstrained file paths

**File:** `src/python/checkpoint.py`, `load_from_file()` and `save_to_file()`

Both functions accept arbitrary `filepath` strings. If these are ever reachable from a WebSocket or HTTP endpoint (the `load_mission` / `save_checkpoint` handlers in `websocket_handlers.py` currently go through `mission_store`, which uses SQLite, so this is not currently exploitable) the risk is path traversal for both read and write.

**Impact:** Currently LOW given current integration (indirect via mission_store). Elevated to HIGH because the public API surface invites direct use; any future caller passing user-supplied paths would introduce path traversal immediately.

**Fix:** Document that `filepath` must be a validated, allowlisted path. Add an assertion at the top of both functions that the resolved path is within a designated checkpoints directory.

---

## MEDIUM

### MED-01 — Injection detection in `llm_sanitizer` can be bypassed with Unicode homoglyphs after NFC normalization

**File:** `src/python/llm_sanitizer.py`, lines 83–96

NFC normalization is applied before pattern matching, which is correct. However, some Unicode look-alike sequences (e.g., Cyrillic "о" substituting for Latin "o" in "ignore") survive NFC unchanged. The regex patterns use ASCII ranges and will not match homoglyph variants.

**Impact:** Sophisticated prompt injection using homoglyphs evades all 10 detection patterns.

**Fix:** Apply NFKC normalization (which maps compatibility variants to their ASCII equivalents) instead of NFC for the injection-detection stage. Alternatively, strip non-ASCII characters before pattern matching (acceptable for tactical text fields).

---

### MED-02 — `scenario_engine.py` `load_scenario` path is not sanitized

**File:** `src/python/scenario_engine.py`, `load_scenario()`, line 86

`yaml_path` is accepted as-is and passed to `open()`. Uses `yaml.safe_load`, which prevents code execution, but path traversal to read arbitrary server files remains possible if callers pass user-supplied paths.

**Impact:** Arbitrary file read if the caller passes user-controlled input. Not currently exploitable via WebSocket (no `load_scenario` WebSocket action exists), but the API is unsafe for future integration.

**Fix:** Same pattern as HIGH-02 — resolve and validate the path is within the `scenarios/` directory before opening.

---

### MED-03 — `report_generator.py` CSV output is vulnerable to CSV injection

**File:** `src/python/report_generator.py`, `_to_str()` and all `*_csv()` methods

Fields like `operator_id`, `target_id`, `outcome`, and `rationale` from audit/engagement records are converted to strings and written to CSV with `quoting=csv.QUOTE_MINIMAL`. A value beginning with `=`, `+`, `-`, or `@` is treated as a formula by Excel/LibreOffice and can execute macros when the exported file is opened.

**Impact:** CSV injection (formula injection) — if an adversary can influence target names or operator IDs, they can inject spreadsheet formulas into exported reports.

**Fix:** In `_to_str()`, prefix values that start with formula-triggering characters to neutralize execution:

```python
def _to_str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "|", "%"):
        s = "'" + s
    return s
```

---

### MED-04 — `rbac.py` module-level `AUTH_DISABLED` and `JWT_SECRET` are read once at import time

**File:** `src/python/rbac.py`, lines 25–26

Both are evaluated at module load, meaning changes to environment variables after startup are not picked up. This is a minor operational concern but also means test isolation requires `monkeypatch` rather than simple env-var setting.

**Impact:** Low operational risk; medium testability risk — incorrect monkeypatching can leak auth state between tests.

**Fix:** Wrap them in a function or use `functools.lru_cache` with cache invalidation. Alternatively, document that a process restart is required for auth config changes.

---

### MED-05 — `hitl_manager.py` `operator_id` is not validated before being stored in audit records

**File:** `src/python/hitl_manager.py` (diff: `_make_decision` now accepts `operator_id`)

The `operator_id` passed to `approve_nomination`, `reject_nomination`, `retask_nomination` comes from WebSocket payload data with no validation of format or length. It is stored verbatim in the decision dict.

**Impact:** Audit trail pollution — an attacker can store arbitrary strings (including control characters, HTML, very long strings) as `operator_id` in the tamper-evident audit log.

**Fix:** Validate `operator_id` in the calling WebSocket handlers: enforce it is a non-empty string matching `[a-zA-Z0-9_\-]{1,64}` before passing to `HITLManager`.

---

## LOW

### LOW-01 — `rbac.py` does not validate JWT `sub` (user_id) field format

**File:** `src/python/rbac.py`, `validate_token()`, lines 153–158

After decoding, `payload["sub"]` is used directly as `user_id` without length or character validation. A malformed token with a very long or control-character-filled `sub` propagates into audit records.

**Fix:** Validate `sub` is a non-empty string ≤ 128 characters after decode.

---

### LOW-02 — `scenario_engine.py` `ScenarioEvent.params` is an unconstrained dict

**File:** `src/python/scenario_engine.py`, `ScenarioEvent`, line 65

`params` is typed as `Dict` with no schema enforcement per event type. A `SPAWN_TARGET` event could omit `target_type` or provide out-of-range coordinates; the engine will pass these params downstream without validation.

**Fix:** Add per-event-type param validation inside `load_scenario()` (e.g., `SPAWN_TARGET` must have `target_type` in a known set and numeric `x`/`y` within theater bounds).

---

### LOW-03 — `sim_controller.py` `set_speed` is not RBAC-gated

**File:** `src/python/sim_controller.py`, `set_speed()`

Changing simulation speed to 50x could cause the simulation loop to overwhelm CPU and produce artificially accelerated engagement outcomes. No role check is enforced (ties back to CRIT-01).

---

### LOW-04 — `checkpoint.py` `save_to_file` does not wrap OS exceptions

**File:** `src/python/checkpoint.py`, `save_to_file()`, line 105

`open(filepath, "w")` will raise a raw `FileNotFoundError` or `PermissionError` if the parent directory does not exist or is not writable. The error is not caught or wrapped in a `CheckpointError`. Callers get an unexpected OS exception type.

**Fix:** Wrap the `open()` call in a try/except and re-raise as `CheckpointError`.

---

## Summary Table

| ID | Severity | File | Issue |
|----|----------|------|-------|
| CRIT-01 | CRITICAL | `rbac.py`, `websocket_handlers.py` | RBAC not integrated — all permission checks are dead code |
| CRIT-02 | CRITICAL | `rbac.py` line 25 | `AUTH_DISABLED` defaults to `true` — production open by default |
| HIGH-01 | HIGH | `rbac.py` line 26 | Hardcoded JWT fallback secret in git history |
| HIGH-02 | HIGH | `websocket_handlers.py` lines 715–735 | `set_roe` path traversal — arbitrary file read |
| HIGH-03 | HIGH | `llm_sanitizer.py` | No input length limit — regex DoS via oversized input |
| HIGH-04 | HIGH | `checkpoint.py` | Unconstrained file paths in public API |
| MED-01 | MEDIUM | `llm_sanitizer.py` | Unicode homoglyph bypass of injection patterns |
| MED-02 | MEDIUM | `scenario_engine.py` | `load_scenario` path not sanitized |
| MED-03 | MEDIUM | `report_generator.py` | CSV formula injection in exported reports |
| MED-04 | MEDIUM | `rbac.py` | Module-level auth config read once at import |
| MED-05 | MEDIUM | `hitl_manager.py` | `operator_id` not validated before audit storage |
| LOW-01 | LOW | `rbac.py` | JWT `sub` field not length/format validated |
| LOW-02 | LOW | `scenario_engine.py` | `ScenarioEvent.params` unconstrained per event type |
| LOW-03 | LOW | `sim_controller.py` | `set_speed(50)` not RBAC-gated |
| LOW-04 | LOW | `checkpoint.py` | `save_to_file` parent dir not checked, raw OS exception |

---

## Priority Fix Order

1. **CRIT-01** — Wire `check_permission` into `handle_payload()` dispatch
2. **CRIT-02** — Change `AUTH_DISABLED` default to `"false"` in `rbac.py`
3. **HIGH-01** — Remove JWT fallback secret; raise on missing `JWT_SECRET`
4. **HIGH-02** — Add path allowlist to `_handle_set_roe`
5. **HIGH-03** — Add `MAX_PROMPT_INPUT = 4096` length cap in `sanitize_prompt_input`
6. **MED-03** — Add CSV formula injection prefix in `_to_str()`
7. **MED-05** — Validate `operator_id` format in WebSocket approval handlers
