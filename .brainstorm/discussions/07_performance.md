# 07 — Performance Analysis

## 10Hz Sim Loop Budget

100ms per tick. Current scale (20 UAVs, 17 targets) is comfortable. Critical paths:

### Per-Tick Work
1. `sim.tick()` — physics + detection + verification + autonomy
2. `assessor.assess()` — every 5s, offloaded via `asyncio.to_thread()`
3. `build_isr_queue()` — every 5s, runs **synchronously** on event loop (not threaded)
4. `sim.get_state()` — called **2-3× per tick** when assessment fires
5. State dict construction with sorted contributions per target
6. `json.dumps()` on full state (~5-10KB)
7. `broadcast()` — parallel send to all dashboard clients
8. `assistant.update()` — scans all targets for state transitions

### Key Finding: get_state() called multiple times
Each call iterates all UAVs, targets, zones, enemy UAVs with embedded `_compute_fov_targets(u)` per UAV (O(U×T)). Three calls per assessment tick = 3× redundant work.

## Complexity Analysis

| Component | Complexity | Scale Impact |
|-----------|-----------|-------------|
| Detection loop (sim_engine) | O(T × U × S) | 510 calls/tick → 5,000 at 50×50 |
| `_compute_fov_targets` | O(U × T) per get_state call | Multiplied by 3× calls |
| `_find_uav/target/enemy_uav` | O(N) linear scan | Called 20+ times/tick — dict would be O(1) |
| `_detect_trigger` | O(U_idle × T) | 500 iterations at 10×50 |
| Swarm assignment | O(T × gaps × U) | Every 50 ticks, acceptable |
| Threat clustering | O(n²) Jarvis march | Every 5s, threaded — OK |
| Verification engine | O(1) per target | No issue |
| Sensor fusion | O(S) per target | Low concern |

## Scalability Limits

| Entities | Expected Behavior |
|----------|------------------|
| 20 UAVs, 17 targets | 5-10ms/tick — comfortable |
| 50 × 50 | 15-25ms — borderline 10Hz |
| 100 × 100 | 50-80ms — **breaks 10Hz** |
| 200 × 200 | 300-400ms — runs at ~2-3Hz |

## WebSocket Bandwidth

- Per-tick payload: 4-8 KB (current), up to 30-50 KB at 100×100
- **No compression applied** — no gzip on WebSocket frames
- **No delta encoding** — full state every tick, even when nothing changed
- 10Hz × 8KB × 5 clients = 400 KB/s sustained

## Frontend Memory Leak

- `SampledPositionProperty` samples added at 10Hz per drone, **never pruned**
- After 10 minutes: 6,000 samples × 20 drones = 120,000 accumulated
- Tether `CallbackProperty` evaluated every Cesium frame (60fps) — 1,200 trig ops/s for 20 drones

## AI Agent Latency

- `_process_new_detection()` called synchronously in sim loop
- Heuristic path: fast (no LLM)
- **If real LLM wired in: blocks event loop 1-3 seconds per call** — all clients miss ticks
- Fix: any LLM call must use `asyncio.to_thread()`

## Memory Growth

| Source | Bounded? |
|--------|----------|
| `target.position_history` | Yes (deque maxlen=60) |
| `TacticalAssistant.message_history` | **No** — unbounded append |
| `TacticalAssistant._nominated` | **No** — grows with all-time targets |
| `_prev_target_states` | **No** — never cleaned |
| `intel_router` history | Yes (max=200) |
| Frontend SampledPositionProperty | **No** — unbounded |
| Event log queue | Yes (max=10,000) |

## I/O Bottleneck

`event_logger.py` opens the log file **on every write** (`with open(log_path, "a")`). At high event rates = bottleneck. Should keep handle open and flush periodically.

## Priority Fixes

### High Impact, Low Effort
1. **Cache `get_state()` once per tick** — eliminates 2 redundant O(U×T) calls (~5 lines)
2. **Replace `_find_uav/target/enemy_uav` with dicts** — O(1) vs O(N), ~15 lines, 10-50% speedup at scale
3. **Move `build_isr_queue()` into assessment thread** — ~3 lines
4. **Fix event logger: keep file handle open** — ~10 lines
5. **Add `detection_range_km` to all target types** — enables early-exit in detection loop

### Medium Impact, Moderate Effort
6. **Vectorize detection loop with numpy** — 10-50× speedup at large scale
7. **Delta-compress WebSocket state** — 50-80% bandwidth reduction
8. **Prune SampledPositionProperty** — prevent frontend memory leak
9. **Replace tether CallbackProperty** — reduce per-frame computation

### Low Impact / High Complexity
10. GPU sensor physics — not warranted until 500+ entities
11. Spatial index for zone lookups — when zones > 100
