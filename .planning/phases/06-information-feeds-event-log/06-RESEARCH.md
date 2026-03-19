# Phase 6: Information Feeds & Event Log - Research

**Researched:** 2026-03-19
**Domain:** WebSocket feed multiplexing, async Python event routing, React real-time UI
**Confidence:** HIGH

## Summary

Phase 6 adds a subscription-based multi-feed layer over the existing single WebSocket connection and extends the event logger. The existing architecture already has the bones: `api_main.py` has a `clients` dict with typed connections, `event_logger.py` has an async JSONL writer, and `useWebSocket.ts` handles all incoming message routing. The work is additive — no structural rewrites needed.

The core backend challenge is multiplexing four logical feeds (STATE, INTEL, SENSOR, COMMAND) over one WebSocket endpoint without adding connection overhead. The approach is per-client subscription state stored in the existing `clients` dict alongside the existing `"type"` field. The `simulation_loop` and `handle_payload` dispatch points in `api_main.py` are the two places where feed events originate; both need to check subscriptions before broadcasting.

The frontend challenge is adding `IntelFeed` and `CommandLog` panels without overwhelming the Zustand store. The existing `assistantMessages` pattern (append-and-trim in the store) is the model to follow. New feed slices go into `SimulationStore.ts` with the same immutable-append pattern.

**Primary recommendation:** Store per-client subscriptions in the existing `clients[websocket]` dict; route feed events at broadcast time using a helper that checks each client's subscription set; keep the single `/ws` endpoint unchanged.

## Standard Stack

### Core (already in project — no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI WebSocket | 0.115.x | WS endpoint, broadcast | Already in use |
| asyncio.Queue | stdlib | JSONL event logger | Already in use |
| Zustand | 4.5.0 | React state slices | Locked decision |
| Blueprint.js `@blueprintjs/core` | 5.x | Card/Table UI components | Locked decision |

### No new dependencies required
All required functionality exists in the current stack. `IntelFeed.tsx` and `CommandLog.tsx` use Blueprint `Card`, `Tag`, and `HTMLTable` primitives already imported elsewhere.

## Architecture Patterns

### Recommended Project Structure
```
src/python/
├── intel_feed.py          # NEW — IntelFeedRouter class
├── event_logger.py        # MODIFY — add feed_event() that both logs + routes
├── api_main.py            # MODIFY — subscription handling, SENSOR_FEED loop
src/frontend-react/src/
├── panels/mission/
│   ├── IntelFeed.tsx      # NEW — INTEL_FEED event stream
│   └── CommandLog.tsx     # NEW — COMMAND_FEED audit trail
├── hooks/
│   └── useWebSocket.ts    # MODIFY — subscribe action on connect, route feed types
├── store/
│   └── SimulationStore.ts # MODIFY — intelEvents[], commandEvents[] slices
```

### Pattern 1: Per-Client Subscription State in `clients` Dict

The `clients` dict already stores `{"type": "DASHBOARD"}` per connection. Extend it:

```python
# In api_main.py — when client subscribes
clients[websocket]["subscriptions"] = set(payload.get("feeds", []))

# In broadcast helper — check subscription
def _client_subscribed(info: dict, feed: str) -> bool:
    subs = info.get("subscriptions")
    if subs is None:
        return True  # legacy client: receive everything
    return feed in subs
```

**Why:** Zero new data structures. Backward compatible — clients without subscriptions get all broadcasts (existing behavior). New clients opt in selectively.

### Pattern 2: IntelFeedRouter as a Thin Event Bus

`intel_feed.py` holds a single class with a queue of recent events and a broadcast callback. `api_main.py` calls `router.emit(event)` at the same sites that currently call `log_event()`. The router both logs and broadcasts:

```python
# intel_feed.py
class IntelFeedRouter:
    def __init__(self, broadcast_fn, max_history: int = 200):
        self._broadcast = broadcast_fn
        self._history: collections.deque = collections.deque(maxlen=max_history)

    async def emit(self, feed_type: str, event: dict) -> None:
        enriched = {
            "feed": feed_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        self._history.append(enriched)
        log_event(feed_type, event)  # JSONL write (non-blocking)
        msg = json.dumps({"type": "FEED_EVENT", "feed": feed_type, "data": enriched})
        await self._broadcast(msg, feed=feed_type)  # subscription-filtered broadcast
```

**Why:** Single call site for both logging and real-time delivery. History deque enables "catch-up" on subscribe.

### Pattern 3: SENSOR_FEED Timing via Second asyncio Loop

SENSOR_FEED runs at 2Hz (every 500ms), independent of the 10Hz STATE loop. Add a second coroutine in the lifespan startup:

```python
async def sensor_feed_loop():
    while True:
        await asyncio.sleep(0.5)
        # for each UAV, emit per-UAV detection snapshot
        for uav in sim.uavs:
            ...
```

**Why:** Decoupled cadence. The existing `simulation_loop` at 10Hz must not be slowed. This mirrors the existing `demo_autopilot()` pattern — a separate task created in `lifespan`.

### Pattern 4: Frontend Feed Slices in SimulationStore

Follow the existing `assistantMessages` append-and-trim pattern:

```typescript
// SimulationStore.ts additions
intelEvents: IntelEvent[];          // max 100
commandEvents: CommandEvent[];      // max 200

addIntelEvent: (e: IntelEvent) => set(state => ({
  intelEvents: [...state.intelEvents, e].slice(-100),
})),
```

In `useWebSocket.ts`, route new message types:

```typescript
if (payload.type === 'FEED_EVENT') {
  const feed = payload.feed;
  if (feed === 'INTEL_FEED') store.getState().addIntelEvent(payload.data);
  if (feed === 'COMMAND_FEED') store.getState().addCommandEvent(payload.data);
  return;
}
```

**Why:** Minimal change to the existing hook. No new WebSocket connections needed.

### Pattern 5: Subscribe Action on Connect

The client sends subscription after IDENTIFY:

```typescript
// useWebSocket.ts — inside ws.onopen
ws.send(JSON.stringify({ type: 'IDENTIFY', client_type: 'DASHBOARD' }));
ws.send(JSON.stringify({ action: 'subscribe', feeds: ['INTEL_FEED', 'COMMAND_FEED'] }));
// SENSOR_FEED: subscribe per UAV later via subscribe_sensor_feed
```

**Why:** IDENTIFY must come first (server awaits it). Subscription is a second message, handled in `handle_payload`. This is already how the server processes action messages.

### Anti-Patterns to Avoid

- **New WebSocket endpoint per feed:** Adds connection multiplexing complexity. The single `/ws` endpoint is the correct model — use logical feed routing over it.
- **Emitting SENSOR_FEED inside the 10Hz loop:** Adds ~UAV-count iterations inside the hot path. Keep SENSOR_FEED in its own 2Hz task.
- **Storing full IntelEvent history in Zustand:** Cap at 100-200 items. The JSONL log is the durable store; Zustand is display-only.
- **Calling `await router.emit()` in synchronous `handle_payload`:** `handle_payload` is async already — just `await` the emit call directly. Do not use `asyncio.create_task` for per-event emission (latency spike risk under load).
- **Mutating the `clients` dict during broadcast iteration:** The existing `broadcast()` already handles removal of failed clients post-gather. Don't add subscription mutation inside the broadcast loop.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Feed history/replay | Custom event store with timestamps | `collections.deque(maxlen=N)` | stdlib, zero-copy, O(1) append |
| JSONL rotation | Custom file manager | Existing `event_logger.py` `_writer_loop` | Already handles date-based filenames |
| Rate-limited broadcast | Custom throttle logic | Existing `RATE_LIMIT_MAX_MESSAGES` in `api_main.py` | Already applies per-client |
| Blueprint feed list UI | Custom virtual scroll | Blueprint `Card` + CSS `overflow-y: auto` with `max-height` | No data volume requires virtualization at 100-event cap |
| Async queue for SENSOR_FEED | Custom async buffer | `asyncio.sleep(0.5)` coroutine reads `sim.uavs` directly | Sim state is already in-memory; no queue needed |

**Key insight:** The sim state is the authoritative in-memory store. SENSOR_FEED just serializes a snapshot of `sim.uavs` per tick — no intermediate queue or buffer is warranted.

## Common Pitfalls

### Pitfall 1: Subscription Sent Before Server Reads IDENTIFY
**What goes wrong:** Server awaits IDENTIFY with a 2-second timeout. If the client sends IDENTIFY + subscribe back-to-back before the server `handle_payload` loop starts, the subscribe message gets processed as if it were IDENTIFY (the `ident_msg = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)` path).
**Why it happens:** `ws.onopen` fires synchronously; two `.send()` calls queue immediately. Server reads the first message as IDENTIFY, but if the payload parsing logic falls into the `else` branch it calls `handle_payload` on the first message — not the second.
**How to avoid:** Add `"subscribe"` to `handle_payload` action handling so it works regardless of when it arrives. The server reads IDENTIFY from the first message, then enters the `while True` loop — the subscribe message will be processed there correctly as long as both are sent in `onopen`.
**Warning signs:** Frontend never receives INTEL_FEED events; server logs show no "subscribe" action processed.

### Pitfall 2: Broadcasting to Modified `clients` Dict During Iteration
**What goes wrong:** `RuntimeError: dictionary changed size during iteration` if subscription state modifies `clients` mid-broadcast.
**Why it happens:** `broadcast()` builds `targets = [ws for ws in clients]` and removes failed sockets afterward. Any modification to `clients` during the gather window can corrupt iteration.
**How to avoid:** Only read `clients[ws]["subscriptions"]` inside `broadcast()`; never add or remove `clients` entries inside the subscription handler — that already happens in the connect/disconnect lifecycle.

### Pitfall 3: SENSOR_FEED Sending Undetected UAV Data
**What goes wrong:** SENSOR_FEED leaks UAV sensor states for UAVs currently in IDLE or non-detection modes, producing noisy zero-detection events.
**Why it happens:** The 2Hz loop iterates all UAVs unconditionally.
**How to avoid:** Only emit SENSOR_FEED for UAVs whose mode is in `("SEARCH", "FOLLOW", "PAINT", "INTERCEPT")` and whose `latest_detections` list is non-empty.

### Pitfall 4: COMMAND_FEED Not Capturing All Command Paths
**What goes wrong:** Some commands logged to JSONL but not emitted to COMMAND_FEED because they use `log_event()` directly rather than `router.emit()`.
**Why it happens:** `api_main.py` has scattered `log_event(...)` calls at each action branch. If only some are updated to use the router, the feed is incomplete.
**How to avoid:** In the plan, replace each existing `log_event("command", ...)` call with `await intel_router.emit("COMMAND_FEED", ...)`. There are currently 5 such calls in `handle_payload` (follow_target, paint_target, intercept_target, cancel_track/scan_area, coa_authorized) plus the verify_target transition.

### Pitfall 5: Zustand Slice Growing Unbounded
**What goes wrong:** `intelEvents` array grows with each 10Hz tick event, causing React rerenders and eventual memory pressure after hours of operation.
**Why it happens:** Forgetting to apply `.slice(-N)` trim in the `addIntelEvent` reducer.
**How to avoid:** Always use `[...state.intelEvents, e].slice(-100)` — same pattern as `assistantMessages`.

## Code Examples

Verified patterns from the existing codebase:

### Subscription Handler in handle_payload
```python
# api_main.py — add to handle_payload
elif action == "subscribe":
    feeds = payload.get("feeds", [])
    if isinstance(feeds, list):
        client_info = clients.get(websocket, {})
        client_info["subscriptions"] = set(feeds)
        # Send history catch-up for subscribed feeds
        if "INTEL_FEED" in feeds:
            history = intel_router.get_history()
            if history:
                await websocket.send_text(json.dumps({
                    "type": "FEED_HISTORY",
                    "feed": "INTEL_FEED",
                    "events": history,
                }))

elif action == "subscribe_sensor_feed":
    uav_ids = payload.get("uav_ids", [])
    if isinstance(uav_ids, list):
        client_info = clients.get(websocket, {})
        client_info.setdefault("subscriptions", set()).add("SENSOR_FEED")
        client_info["sensor_feed_uav_ids"] = set(uav_ids)
```

### Subscription-Filtered Broadcast
```python
# Modified broadcast() signature addition
async def broadcast(message: str, target_type: str = None,
                    sender: WebSocket = None, feed: str = None):
    targets = []
    for ws, info in clients.items():
        if ws == sender:
            continue
        if target_type and info.get("type") != target_type:
            continue
        if feed is not None:
            subs = info.get("subscriptions")
            if subs is not None and feed not in subs:
                continue
        targets.append(ws)
    ...
```

### IntelFeed.tsx Core Structure
```typescript
// Source: matches existing AssistantWidget.tsx pattern
import { useSimStore } from '../../store/SimulationStore';
import { Card, Tag, Intent } from '@blueprintjs/core';

const FEED_INTENT: Record<string, Intent> = {
  DETECTED: Intent.PRIMARY,
  CLASSIFIED: Intent.WARNING,
  VERIFIED: Intent.SUCCESS,
  NOMINATED: Intent.DANGER,
};

export function IntelFeed() {
  const events = useSimStore(s => s.intelEvents);

  return (
    <Card style={{ padding: 8 }}>
      <div style={{ fontWeight: 700, fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>
        INTEL FEED
      </div>
      <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
        {events.slice().reverse().map((e, i) => (
          <div key={i} style={{ fontSize: 11, display: 'flex', gap: 6, alignItems: 'flex-start' }}>
            <span style={{ color: '#475569', flexShrink: 0 }}>{e.timestamp?.slice(11, 19)}</span>
            <Tag minimal intent={FEED_INTENT[e.event] || Intent.NONE} style={{ fontSize: 10 }}>
              {e.event}
            </Tag>
            <span style={{ color: '#94a3b8' }}>{e.summary}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
```

### CommandLog.tsx Core Structure
```typescript
// Source: matches Blueprint HTMLTable usage in StrikeBoard.tsx
import { HTMLTable, Tag, Intent } from '@blueprintjs/core';

export function CommandLog() {
  const events = useSimStore(s => s.commandEvents);

  return (
    <Card style={{ padding: 8 }}>
      <div style={{ fontWeight: 700, fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>
        COMMAND LOG
      </div>
      <div style={{ maxHeight: 200, overflowY: 'auto' }}>
        <HTMLTable condensed style={{ width: '100%', fontSize: 11 }}>
          <tbody>
            {events.slice().reverse().map((e, i) => (
              <tr key={i}>
                <td style={{ color: '#475569' }}>{e.timestamp?.slice(11, 19)}</td>
                <td><Tag minimal>{e.action}</Tag></td>
                <td style={{ color: '#94a3b8' }}>{e.source || 'operator'}</td>
              </tr>
            ))}
          </tbody>
        </HTMLTable>
      </div>
    </Card>
  );
}
```

### event_logger.py Enhancement for Retention Control
```python
# Add configurable retention: keep N days of logs
import os, glob

def rotate_logs(max_days: int = 7) -> None:
    """Delete JSONL files older than max_days. Call from start_logger."""
    files = sorted(glob.glob(str(LOG_DIR / "events-*.jsonl")))
    if len(files) > max_days:
        for old in files[:-max_days]:
            try:
                os.remove(old)
            except OSError:
                pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single broadcast to all DASHBOARD clients | Subscription-filtered broadcast per feed | Phase 6 | Clients receive only opted-in data |
| `log_event()` direct calls scattered in handle_payload | `intel_router.emit()` combining log + broadcast | Phase 6 | Single call site per event |
| No event history on reconnect | `get_history()` catch-up on subscribe | Phase 6 | Clients get recent events on reconnect |

**Deprecated/outdated:**
- Scattered `log_event("command", ...)` calls: replaced by `intel_router.emit("COMMAND_FEED", ...)` in Phase 6.

## Open Questions

1. **SENSOR_FEED subscription per UAV ID vs. all UAVs**
   - What we know: Phase description specifies `subscribe_sensor_feed` with `uav_ids` list
   - What's unclear: Is per-UAV filtering needed for Phase 6 or can all-UAVs be the default?
   - Recommendation: Implement per-UAV filter in server but have frontend subscribe to all UAVs initially; the per-UAV filter exists for future consumer targeting.

2. **DroneCam.tsx fusion overlay scope**
   - What we know: Phase description says "overlay fused confidence, verification status on HUD"
   - What's unclear: Whether this means text overlays on the canvas or React elements positioned over the canvas
   - Recommendation: Use React elements positioned `absolute` over the canvas (same pattern as the PIP close button) — no canvas drawing API needed, stays in React's render tree.

3. **IntelFeed and CommandLog placement in tabs**
   - What we know: Phase adds two new panels; existing tabs are MISSION, ASSETS, ENEMIES
   - What's unclear: Whether they go in MISSION tab (alongside StrikeBoard/AssistantWidget) or a new INTEL tab
   - Recommendation: Add them to the MISSION tab below AssistantWidget (consistent with current info-flow layout). A new tab adds navigation overhead for components that display live event streams.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `src/python/tests/conftest.py` |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_feeds.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-5-STATE | STATE_FEED broadcast to subscribed clients | integration | `pytest tests/test_feeds.py::test_state_feed_subscription -x` | Wave 0 |
| FR-5-INTEL | INTEL_FEED emits on target state transition | unit | `pytest tests/test_feeds.py::test_intel_feed_state_transition -x` | Wave 0 |
| FR-5-SENSOR | SENSOR_FEED emits at 2Hz per tracked UAV | unit | `pytest tests/test_feeds.py::test_sensor_feed_cadence -x` | Wave 0 |
| FR-5-COMMAND | COMMAND_FEED captures all command actions | unit | `pytest tests/test_feeds.py::test_command_feed_coverage -x` | Wave 0 |
| FR-5-SUB | subscribe action filters broadcast to subscribed feeds | integration | `pytest tests/test_feeds.py::test_subscription_filtering -x` | Wave 0 |
| FR-10 | event_logger writes feed events to JSONL | unit | `pytest tests/test_event_logger.py -x` (existing, extend) | exists |
| FR-10-ROTATION | Log rotation deletes files older than max_days | unit | `pytest tests/test_feeds.py::test_log_rotation -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_feeds.py -x`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/python/tests/test_feeds.py` — covers FR-5-STATE, FR-5-INTEL, FR-5-SENSOR, FR-5-COMMAND, FR-5-SUB, FR-10-ROTATION

## Sources

### Primary (HIGH confidence)
- Existing codebase (`api_main.py`) — broadcast pattern, clients dict, handle_payload structure
- Existing codebase (`event_logger.py`) — async JSONL queue pattern
- Existing codebase (`useWebSocket.ts`) — onmessage routing, store dispatch pattern
- Existing codebase (`SimulationStore.ts`) — Zustand slice pattern, addAssistantMessage trim pattern
- Existing codebase (`tests/test_event_logger.py`) — test fixture approach for logger reset

### Secondary (MEDIUM confidence)
- FastAPI WebSocket docs — single endpoint with message-based multiplexing is standard pattern
- Zustand docs — `create()` with slices, immutable state updates

### Tertiary (LOW confidence)
- None — all findings are based on direct codebase inspection

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all verified in codebase
- Architecture: HIGH — directly derived from existing `api_main.py` patterns
- Pitfalls: HIGH — identified from direct reading of `handle_payload` branching and `broadcast()` implementation
- Frontend patterns: HIGH — derived from existing `AssistantWidget.tsx` and `SimulationStore.ts` patterns

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable codebase, 30-day window)
