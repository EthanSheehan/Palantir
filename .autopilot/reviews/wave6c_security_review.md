# Wave 6C-Alpha Security Review

**Reviewer:** Security Reviewer Agent
**Date:** 2026-03-26
**Scope:** All new and modified files in Wave 6C-Alpha

---

## Summary

| Severity | Count |
|----------|-------|
| HIGH     | 2     |
| MEDIUM   | 6     |
| LOW      | 4     |
| INFO     | 3     |

---

## HIGH Findings

### H-1: `/metrics` endpoint is unauthenticated and publicly accessible
**File:** `src/python/api_main.py:326-332`
**Description:** The `/metrics` endpoint returns Prometheus-format operational intelligence: connected client count, autonomy level (MANUAL/SUPERVISED/AUTONOMOUS), active target count, drone count, HITL approval/rejection counts, and tick performance data. This endpoint has no authentication check — it is accessible to any unauthenticated caller, including over the network when `host=0.0.0.0`.

For a C2 system, the current autonomy level and number of active targets/drones is operationally sensitive information. An adversary who can reach port 8000 can poll this endpoint to infer mission state without any credentials.

**Recommendation:** Gate the `/metrics` endpoint behind auth or restrict it to localhost-only via a middleware dependency. At minimum, add an IP-allowlist check or require the `auth_manager` token check that WebSocket actions already use. A Prometheus scraper should use a dedicated service account token, not open access.

```python
# Option A: Require internal-only (before the route handler)
@app.get("/metrics")
async def get_metrics(request: Request):
    if request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    ...

# Option B: Add a bearer token dependency
```

---

### H-2: `palantir:send` event bridge accepts arbitrary WebSocket payloads from Cesium hooks without validation
**File:** `src/frontend-react/src/App.tsx:29-33`
**Description:** The `palantir:send` event listener in `App.tsx` forwards `(e as CustomEvent).detail` directly to `sendMessage()` — which calls `ws.send(JSON.stringify(msg))` — without any validation of the message shape or permitted action types. Custom events dispatched on `window` are reachable from any JavaScript running in the same origin, including third-party Cesium ion scripts or injected scripts.

If an attacker achieves XSS or can load a malicious Cesium plugin, they can call:
```js
window.dispatchEvent(new CustomEvent('palantir:send', {
  detail: { action: 'authorize_coa', entry_id: '...', ... }
}))
```
to send arbitrary WebSocket actions — including `authorize_coa`, `set_autonomy_level`, `reset`, or `approve_nomination` — bypassing the UI safety gates entirely (including the AutonomyBriefingDialog confirmation flow).

**Recommendation:** Validate the action field in the `onSend` handler against an allowlist of actions that are legitimate for Cesium-originated events (e.g., `move_drone`, `scan_area`, `follow_target`, `paint_target`). Reject or log anything outside that set.

```typescript
const CESIUM_ALLOWED_ACTIONS = new Set([
  'move_drone', 'scan_area', 'follow_target',
  'paint_target', 'intercept_target',
]);

function onSend(e: Event) {
  const detail = (e as CustomEvent).detail;
  if (!detail?.action || !CESIUM_ALLOWED_ACTIONS.has(detail.action)) {
    console.warn('palantir:send blocked: unauthorized action', detail?.action);
    return;
  }
  sendMessage(detail);
}
```

---

## MEDIUM Findings

### M-1: `CommandPalette` bypasses the AutonomyBriefingDialog confirmation gate for AUTONOMOUS mode
**File:** `src/frontend-react/src/overlays/CommandPalette.tsx:88-92`
**Description:** The `AutonomyToggle` component correctly gates `set_autonomy_level AUTONOMOUS` behind a dialog requiring explicit acknowledgment. However, the `CommandPalette` exposes a "Set Autonomy: AUTONOMOUS" command that calls `sendMessage({ action: 'set_autonomy_level', level: 'AUTONOMOUS' })` directly, bypassing the briefing dialog entirely. An operator could escalate to full autonomous engagement via a single keypress (Ctrl+P → type "auto" → Enter) with no safety confirmation.

**Recommendation:** Replace the direct `sendMessage` call in the AUTONOMOUS command with the same confirmation flow used by `AutonomyToggle`. Either emit a window event that the `AutonomyToggle` listens to, or lift the briefing state to a shared context. The SUPERVISED and MANUAL commands can remain direct.

---

### M-2: Missing `ssl_certfile` / `ssl_keyfile` path traversal validation
**File:** `src/python/config.py:113-120`
**Description:** The `ssl_certfile` and `ssl_keyfile` fields accept arbitrary path strings from the environment with no path sanitization. While these are loaded at startup (not per-request), a misconfigured deployment with a writable `.env` file and a shared host could allow an attacker who controls the environment to point the keyfile at any readable file on disk, potentially reading sensitive files during TLS handshake negotiation or causing confusing error messages that reveal filesystem structure.

**Recommendation:** Add a `@field_validator` that resolves the path to absolute form and verifies it exists and is a regular file (not a directory or device) at settings-load time. This also catches misconfigured deployments early with a clear error.

```python
from pydantic import field_validator
import pathlib

@field_validator("ssl_certfile", "ssl_keyfile", mode="before")
@classmethod
def _validate_path(cls, v):
    if v is None:
        return v
    p = pathlib.Path(v).resolve()
    if not p.is_file():
        raise ValueError(f"SSL file path does not exist or is not a file: {v}")
    return str(p)
```

---

### M-3: `useWebSocket` uses unvalidated JSON from server — no error handling on `JSON.parse`
**File:** `src/frontend-react/src/hooks/useWebSocket.ts:38`
**Description:** `JSON.parse(event.data)` is called without a try/catch. A malformed message from the server (or a MITM injection if TLS is not enabled) will throw an unhandled exception that silently kills the `onmessage` handler, disconnecting the UI from further state updates without any user-visible error. More critically, there is no schema validation on the parsed payload — fields like `payload.data` are passed directly into the Zustand store without checking types.

**Recommendation:** Wrap the parse in try/catch and add basic shape guards before dispatching to the store.

---

### M-4: CesiumContextMenu exposes `approve_nomination` as a right-click action with no confirmation
**File:** `src/frontend-react/src/cesium/CesiumContextMenu.tsx:88-94`
**Description:** The context menu on map targets includes a "Nominate" option that immediately calls `sendMessage({ action: 'approve_nomination', target_id: numericId })` on click with no confirmation dialog. A misclick on the globe can approve a weapons nomination for the wrong target without any undo mechanism. Given that this is a lethal engagement action, the absence of a confirmation step is a significant usability and safety concern.

**Recommendation:** Add a confirmation dialog or at minimum a second-click confirmation (double-click to approve, or an "Are you sure?" Blueprint `Alert`). This is consistent with the batched APPROVE ALL confirmation in `StrikeBoard.tsx`.

---

### M-5: `autonomy_level` string in `metrics.py` is unvalidated and passed into Prometheus output
**File:** `src/python/metrics.py:138-212`
**Description:** The `autonomy_level` value passed to `update_gauges()` is interpolated into the Prometheus text output at line 212:
```python
lines.append(f'palantir_autonomy_level{{level="{level}"}} {active}')
```
The `level` values come from `_AUTONOMY_LEVELS = ("MANUAL", "SUPERVISED", "AUTONOMOUS")` which are safe constants — however the `autonomy_level` stored in `_state` comes from callers (e.g., `update_gauges(autonomy_level=sim.autonomy_level)`). If `sim.autonomy_level` were ever set to an unexpected value (e.g., via a malformed WebSocket action or future refactor), the string would be interpolated into the metric output without sanitization.

The immediate risk is low because the one-hot labels are from the constant tuple, but the stored `autonomy_level` string used in `MetricsSnapshot` could contain newlines or special characters that corrupt the Prometheus format. This could cause a monitoring scraper to misparse the entire metrics output.

**Recommendation:** Sanitize `autonomy_level` when stored — clamp to the known set of values or strip/reject non-alphanumeric characters. One line in `update_gauges`:
```python
_state.autonomy_level = autonomy_level if autonomy_level in ("MANUAL", "SUPERVISED", "AUTONOMOUS") else "MANUAL"
```

---

### M-6: `demo_token` defaults to the string `"dev"` and is not excluded from production configs
**File:** `src/python/config.py:131-133`
**Description:** The `demo_token` field has a hardcoded default of `"dev"` which acts as a universal bypass token that authenticates as `DASHBOARD` tier. This default is appropriate for development but there is no validation preventing it from being used in production (e.g., when `auth_enabled=True` but `demo_token` is left at its default).

An operator who enables auth but forgets to rotate the demo token leaves a known credential in place. The token is also logged via `logger.info("client_identified", ...)` on every connection, which means it appears in log files.

**Recommendation:** Add a `@model_validator` that raises a warning (or error in strict mode) if `auth_enabled=True` and `demo_token` is still the default value `"dev"`. Consider also marking this field as `exclude=True` in Pydantic to prevent it from appearing in any serialized config dumps.

---

## LOW Findings

### L-1: `_is_origin_allowed` treats missing `Origin` header as allowed (non-browser clients)
**File:** `src/python/api_main.py:204-206`
**Description:** Missing `Origin` header returns `True`. This is documented behavior intended for non-browser simulator clients but means any raw TCP/WebSocket client with no `Origin` header bypasses the origin check entirely. Combined with no auth in development mode, this allows unrestricted tool-based access.

**Recommendation:** No change needed for current threat model (local dev + auth-gated production), but document the assumption explicitly in the function docstring and consider logging `origin=None` connections at DEBUG level for audit purposes.

---

### L-2: `StrikeBoard` batch "APPROVE ALL" sends one WebSocket message per pending entry in a tight loop
**File:** `src/frontend-react/src/panels/mission/StrikeBoard.tsx:25-31`
**Description:** The `APPROVE_ALL` handler iterates over all pending entries and calls `sendMessage()` for each in a synchronous for-loop, potentially sending N messages in rapid succession. If the backend rate limit (`RATE_LIMIT_MAX_MESSAGES=30` per second) is hit, some approvals will be silently dropped with only a "Rate limit exceeded" WebSocket error. The UI has no feedback mechanism for dropped messages in this flow.

**Recommendation:** Either batch these into a single `approve_nominations` action (preferred), or add a small delay between sends, or handle the rate-limit error response in the UI and show a toast.

---

### L-3: `EngagementHistory` uses `ev.entry_id` as a React `key` with fallback to timestamp+action concatenation
**File:** `src/frontend-react/src/panels/assessment/EngagementHistory.tsx:62`
**Description:** The key `ev.entry_id || \`${ev.timestamp}-${ev.action}\`` could produce duplicate keys if two events share the same timestamp and action type. This is a React rendering issue, not a direct security vulnerability, but duplicate keys can cause the component to display stale data silently.

---

### L-4: `CommandPalette` stores command history in `localStorage` by command ID
**File:** `src/frontend-react/src/overlays/CommandPalette.tsx:5-27`
**Description:** Command history is stored in `localStorage` under key `palantir:cmd_history`. This persists sensitive operational history (which targets were approved, which autonomy states were set) in plaintext browser storage, readable by any script with same-origin access. In a shared workstation/kiosk scenario, this leaks recent operator actions.

**Recommendation:** Use `sessionStorage` instead of `localStorage` so history does not persist across browser sessions, or clear history on logout/disconnect.

---

## INFO / Observations

### I-1: TLS paths accepted at config load time but never validated for permissions
The `_validate_ssl` validator checks that both `ssl_certfile` and `ssl_keyfile` are non-empty strings, but does not check file existence or readability. A typo in the path results in an uvicorn startup error rather than a clear config validation error. See M-2 for the recommended fix.

### I-2: Prometheus histogram implementation uses a single `le="0.1"` bucket for all counts
**File:** `src/python/metrics.py:158-161`
The histogram emits both `le="0.1"` and `le="+Inf"` with identical values (`tick_count`). This means the Prometheus server will treat every tick as falling below 0.1s. Ticks that actually exceed 100ms will not be captured in the right bucket. This is a monitoring correctness issue — it will make alerts based on tick latency buckets unreliable — but not a security concern.

### I-3: `useWebSocket` hardcodes `ws://` scheme, disabling TLS in the frontend
**File:** `src/frontend-react/src/hooks/useWebSocket.ts:21`
```typescript
const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws`);
```
Even if the backend has `ssl_enabled=True`, the frontend will still connect over unencrypted WebSocket. This means enabling server-side TLS alone does not protect the WebSocket connection. The scheme should be derived from `window.location.protocol` (`wss://` when served over HTTPS).

```typescript
const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${scheme}://${window.location.hostname}:8000/ws`);
```

---

## Files Reviewed

| File | Status |
|------|--------|
| `src/python/config.py` | Reviewed — M-2, M-6, I-1 |
| `src/python/api_main.py` | Reviewed — H-1, L-1 |
| `src/python/metrics.py` | Reviewed — M-5, I-2 |
| `src/frontend-react/src/App.tsx` | Reviewed — H-2 |
| `src/frontend-react/src/overlays/CommandPalette.tsx` | Reviewed — M-1, L-4 |
| `src/frontend-react/src/panels/mission/AutonomyBriefingDialog.tsx` | Reviewed — no findings (gate logic correct) |
| `src/frontend-react/src/panels/mission/AutonomyToggle.tsx` | Reviewed — no findings |
| `src/frontend-react/src/panels/mission/StrikeBoard.tsx` | Reviewed — L-2 |
| `src/frontend-react/src/panels/assessment/AssessmentTab.tsx` | Reviewed — no findings |
| `src/frontend-react/src/panels/assessment/EngagementHistory.tsx` | Reviewed — L-3 |
| `src/frontend-react/src/panels/assets/SwarmHealthPanel.tsx` | Reviewed — no findings |
| `src/frontend-react/src/cesium/CesiumContainer.tsx` | Reviewed — no findings |
| `src/frontend-react/src/cesium/CesiumContextMenu.tsx` | Reviewed — M-4 |
| `src/frontend-react/src/components/ConnectionStatus.tsx` | Reviewed — no findings |
| `src/frontend-react/src/overlays/KillChainRibbon.tsx` | Reviewed — no findings |
| `src/frontend-react/src/overlays/MapLegend.tsx` | Reviewed — no findings |
| `src/frontend-react/src/hooks/useWebSocket.ts` | Reviewed — M-3, I-3 |
| `src/python/tests/test_metrics.py` | Reviewed — no findings |
| `src/python/tests/test_tls_config.py` | Reviewed — no findings |

---

## Priority Fix Order

1. **H-1** — Protect `/metrics` endpoint (auth or localhost-only gate)
2. **H-2** — Allowlist `palantir:send` event bridge actions
3. **M-1** — Route CommandPalette AUTONOMOUS command through briefing dialog
4. **M-3** — Wrap `JSON.parse` in try/catch in `useWebSocket`
5. **M-5** — Clamp `autonomy_level` to known values in `update_gauges`
6. **M-6** — Warn/error if `auth_enabled=True` and `demo_token="dev"`
7. **I-3** — Fix `ws://` hardcode to derive scheme from page protocol
8. **M-2** — Add SSL path existence validation in config
9. **M-4** — Add nomination confirmation in CesiumContextMenu
10. **L-2** — Handle rate-limit dropped messages in batch approve flow
