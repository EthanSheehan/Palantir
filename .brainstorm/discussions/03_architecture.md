# 03 — Architecture Audit

## File Sizes

**Over 800 lines (MUST split):**

| File | Lines | Issue |
|------|-------|-------|
| `sim_engine.py` | 1,553 | God module — physics + detection + fusion + verification + swarm + autonomy |
| `api_main.py` | 1,113 | God file — WebSocket + sim loop + autopilot + handlers + REST + agents |

**Over 400 lines (flag):**

| File | Lines |
|------|-------|
| `vision/video_simulator.py` | 666 |
| `tests/test_drone_modes.py` | 746 |
| `agents/tactical_planner.py` | 442 |
| `llm_adapter.py` | 455 |

## God Objects

### SimulationModel (sim_engine.py, ~1,042 lines of class body)
Does: UAV physics (11 modes), target physics (5 behaviors), enemy UAV sim (4 modes), sensor detection, fusion orchestration, verification orchestration, zone/grid management, swarm orchestration, autonomy state machine, theater config, ISR dispatch, state serialization.

Should be: `UAVPhysicsEngine`, `TargetBehaviorEngine`, `EnemyUAVEngine`, `DetectionPipeline`, `AutonomyController`, thin `SimulationOrchestrator`.

### api_main.py (1,113 lines)
Does: WebSocket connection management, 10Hz sim loop, assessment loop, demo autopilot, 25+ action handlers (200-line if/elif), 4 REST endpoints, TacticalAssistant class, agent instantiation, intel feed detection, sensor feed loop.

## Coupling Issues

- `api_main.py` accesses private SimulationModel methods: `sim._find_target()`, `sim._find_uav()`, `sim._last_assessment`
- `tactical_planner.py` imports from `hitl_manager` — agent layer coupled to HITL state
- `handle_payload()` is a 200-line if/elif dispatch tree — every new command requires editing one function

## Separation of Concerns Violations

- `demo_autopilot()` mixes autonomous decision logic with WebSocket broadcasting — untestable without mocking WebSocket
- `TacticalAssistant.update()` has side effect of mutating `_nominated` set — "message generator" secretly does HITL nomination
- `_process_new_detection()` labeled as "process detection" but calls `hitl.nominate_target()` as side effect
- `verify_target` action handler directly mutates `target.state` — bypasses verification engine state machine
- `sim_engine.py` `tick()` method: 250 lines, 11 sequential steps as comment blocks not method calls

## Dead Code

- `pipeline.py` `hitl_approve()` uses `input()` — blocking stdin, never used in WebSocket flow
- The entire F2T2EAPipeline is effectively dead code in the running system

## State Management Risks

- **Real data race:** `asyncio.to_thread()` for assessment reads `sim` state while main loop mutates it — different threads, no locks
- Module-level mutable globals: `sim`, `hitl`, `clients`, `_prev_target_states`, `_cached_assessment`
- `demo_autopilot()` and `simulation_loop()` share `sim` and `hitl` without synchronization

## Autonomy Level Issues

1. Swarm coordinator ignores autonomy level entirely (comment: "autonomy tier integration deferred")
2. `AUTONOMOUS_TRANSITIONS` table covers only 2 triggers — most mode transitions never fire autonomously
3. Autonomy level reset to MANUAL on theater switch (recreates SimulationModel)
4. `demo_autopilot()` is the actual AUTONOMOUS mode — separate from formal autonomy in sim_engine
5. No audit trail for autonomous actions — auto-approval on timeout not logged to intel feed

## Configuration Issues

- ~25 magic constants in sim_engine.py not in PalantirSettings
- CORS allow_origins hardcoded to localhost:3000
- Demo autopilot delays are local constants, not configurable

## Error Handling

- Silent `except ValueError: pass` in autopilot COA authorization (line 426)
- `_process_new_detection()` uses `str(exc)` instead of `logger.exception()` — loses stack trace
- `broadcast()` silently removes failed clients without logging IDs

## Summary by Urgency

| Issue | Severity |
|-------|----------|
| asyncio.to_thread reads sim while main loop mutates | HIGH |
| api_main.py 1113-line God file | HIGH |
| sim_engine.py 1553-line God module | HIGH |
| demo_autopilot() untestable, coupled to globals | HIGH |
| Swarm coordinator ignores autonomy | MEDIUM |
| Autonomy reset on theater switch | MEDIUM |
| Silent ValueError pass in autopilot | MEDIUM |
| handle_payload 200-line if/elif | MEDIUM |
| verify_target bypasses verification engine | MEDIUM |
