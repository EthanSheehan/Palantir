# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Swarm Upgrade

**Shipped:** 2026-03-20
**Phases:** 11 | **Plans:** 37 | **Sessions:** ~10

### What Was Built
- Full React + TypeScript + Blueprint frontend replacing vanilla JS
- Multi-sensor fusion engine with complementary confidence formula
- 8-state target verification pipeline with regression
- 4 new drone modes + 3-tier autonomy system
- Enemy UAV simulation with evasion/intercept/jamming
- Swarm coordination with auto-sensor dispatching
- Subscription-based feed system (INTEL/SENSOR/COMMAND)
- Battlespace assessment (clustering, gaps, corridors)
- Adaptive ISR with threat-adaptive coverage
- 6 map visualization modes with layer toggles
- Multi-sensor drone feeds with 4 layout modes

### What Worked
- GSD wave-based parallel execution kept context fresh per plan
- Pure-function modules (sensor_fusion, verification_engine, battlespace_assessment) made testing trivial
- Frozen dataclasses prevented mutation bugs across the board
- Phase dependency ordering (fusion → verification → modes → swarm) meant each phase built cleanly on the last
- 10Hz WebSocket push model scaled well to 11 phases of additional data
- React + Blueprint migration in Phase 0 paid dividends — every subsequent phase added UI cleanly

### What Was Inefficient
- Phase 0 ROADMAP had stale file paths (referenced `src/frontend/` instead of `src/frontend-react/`)
- Some plan summaries had null one_liner fields — gsd-tools summary-extract returned nothing
- Phase 8/9/10 STATUS in STATE.md still showed "PLANNED" after execution — state updates lagged

### Patterns Established
- Window custom events (`grid_sentinel:send`, etc.) for Cesium→React bridge
- `?? true` fallback pattern for backward-compatible layer visibility
- Module-level constants for mode physics (`_SENSOR_QUALITY_MAP`, `AUTONOMOUS_TRANSITIONS`)
- GroundPrimitive rebuild-on-count-change pattern for Cesium layers
- Diff-based entity management (add/remove changed only) for polyline layers

### Key Lessons
1. Pure functions + frozen dataclasses = reliable simulation modules
2. CesiumJS needs imperative hooks (not resium) for SampledPositionProperty and GroundPrimitive
3. Blueprint SegmentedControl quirks (mutable arrays, missing small prop) — test installed version
4. 10Hz tick rate is fine for state broadcast but assessment/swarm should throttle to 5s
5. No StrictMode with Cesium — double-mount breaks Viewer lifecycle

### Cost Observations
- Model mix: ~30% opus (planning), ~60% sonnet (execution), ~10% haiku (research/docs)
- Sessions: ~10 across 6 days
- Notable: GSD parallel wave execution significantly reduced wall-clock time per phase

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~10 | 11 | GSD wave execution, pure-function modules |

### Cumulative Quality

| Milestone | Tests | Coverage | Pure Modules |
|-----------|-------|----------|-------------|
| v1.0 | 80+ | ~80% | 5 (fusion, verification, swarm, battlespace, isr_priority) |

### Top Lessons (Verified Across Milestones)

1. Pure functions + frozen dataclasses = reliable, testable simulation modules
2. GSD fresh-context subagents prevent context rot across 37 plans
