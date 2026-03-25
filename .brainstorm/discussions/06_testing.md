# 06 — Testing & Validation Analysis

## Current State
- **475 tests** across **23 test files**
- Framework: pytest + pytest-asyncio
- No CI/CD pipeline (no .github/workflows/)
- Playwright E2E: 11 specs targeting **legacy vanilla JS frontend** (not React)
- Zero React component/unit tests (no Vitest)

## Coverage by Module

| Module | Tests | Quality |
|--------|-------|---------|
| sim_engine (drone modes) | 67 | Good — 3-tier autonomy, transitions |
| isr_priority | 31 | Good — urgency scoring, queue sorting |
| enemy_uavs | 31 | Good — physics, intercept, confidence |
| sensor_model | 36 | Good — Pd, RCS, weather, boundaries |
| agent wiring (isr/strategy) | 37 | Good — heuristic + LLM fallback |
| effectors_agent | 27 | Good — Pk, damage, BDA |
| intel_feed + event_logger | 15 | Adequate — routing, subscriptions |
| verification_engine | 27 | Good — state machine, regression |
| sim_integration | 24 | Good — detection, fusion, assessment |
| swarm_coordinator | 13 | Adequate — assignment, expiry |
| battlespace_assessment | 21 | Good — clustering, gaps, corridors |
| hitl_manager | 14 | Good — nominations, COAs, immutability |
| llm_adapter | 24 | Good — fallback, parsing |
| sensor_fusion | 13 | Good — formula, dedup, clamping |
| theater_loader | 15 | Good — all 3 theaters, validation |

## CRITICAL GAPS — Zero Tests

| Module | Lines | Why Critical |
|--------|-------|-------------|
| **demo_autopilot()** | 160 | Full autonomous kill chain — ZERO tests |
| **tactical_planner.py** | 442 | COA generation, 8 pure functions — ZERO tests |
| **handle_payload()** | 212 | 20+ action handlers, only 2 tested |
| **simulation_loop()** | 90 | ISR queue, assessment scheduling |
| **F2T2EAPipeline** | 124 | Kill chain orchestration |
| **performance_auditor.py** | 182 | Confidence drift detection |
| **React frontend** | ~40 components | Zero Vitest/RTL tests |

## Tests Needed for Autopilot

### demo_autopilot() Unit Tests
- test_demo_autopilot_approves_pending_after_delay
- test_demo_autopilot_dispatches_nearest_uav
- test_demo_autopilot_escalates_follow_to_paint
- test_demo_autopilot_generates_coas_after_paint
- test_demo_autopilot_authorizes_best_coa
- test_demo_autopilot_auto_intercepts_enemy_above_threshold
- test_demo_autopilot_skips_already_inflight
- test_demo_autopilot_no_op_when_no_available_uav

### Autonomous Mode Integration
- test_full_kill_chain_auto_mode_completes (UNDETECTED → AUTHORIZED)
- test_supervised_requires_approval
- test_supervised_auto_approves_on_timeout
- test_autonomous_fleet_with_manual_override

### Tactical Planner
- test_generate_coas_returns_three_sorted_by_composite
- test_haversine_km_known_distance
- test_score_asset_prefers_closer_faster
- test_compute_composite_higher_pk_wins

## Property-Based Tests (hypothesis)

| Property | Module | Invariant |
|----------|--------|-----------|
| Fusion monotonicity | sensor_fusion | Adding contribution never decreases confidence |
| Confidence bounded | sensor_fusion | Output always in [0.0, 1.0] |
| State irreversibility | verification_engine | Terminal states never regress |
| Idle guard | swarm_coordinator | Idle count never drops below min |
| Priority ordering | isr_priority | Queue always sorted descending |
| Bounds containment | sim_engine | UAV positions stay within theater |

## Regression Tests Needed
1. DEMO_FAST full kill chain completes faster than normal
2. get_state() golden snapshot — all fields preserved across refactors
3. Theater initialization with correct UAV/target counts from YAML
4. Enemy UAV confidence degrades when out of sensor range
5. Swarm task expiry after 120s
6. Full state machine: UNDETECTED → NOMINATED → AUTHORIZED

## Benchmark Scenarios (Missing)

| Scenario | Metric |
|----------|--------|
| 100 drones, 50 targets, 1000 ticks | tick time < 100ms |
| SwarmCoordinator 20 targets × 100 UAVs | assignment < 10ms |
| BattlespaceAssessor 50 targets, 100 zones | assess < 50ms |
| fuse_detections 100 contributions | fusion < 1ms |
| Broadcast to 10 clients | broadcast < 10ms |

## Frontend Testing — Completely Absent
- No Vitest configuration
- No @testing-library/react setup
- No .test.tsx or .spec.tsx files
- Playwright E2E targets legacy frontend, not React
- Need: SimulationStore tests, component tests, Cesium hook tests

## CI/CD — Nonexistent
- No .github/workflows/
- No coverage reporting (no pytest-cov config)
- No linting/type-checking in pipeline
- No frontend build validation
- No security scanning

## Prioritized Action Plan

**P0 — Blocking autopilot quality:**
1. Tests for demo_autopilot() with AsyncMock
2. Tests for all handle_payload() action branches
3. Tests for tactical_planner COA generation

**P1 — High value:**
4. Property tests with hypothesis
5. Full kill chain integration test
6. Golden snapshot for get_state() schema
7. Vitest + RTL setup for React

**P2 — Infrastructure:**
8. GitHub Actions CI: pytest + coverage 80% + Playwright
9. pytest-benchmark for tick() performance
10. Port Playwright E2E to React frontend

**P3 — Completeness:**
11. performance_auditor tests
12. F2T2EAPipeline.run() with auto_approve
13. WebSocket integration via FastAPI TestClient
