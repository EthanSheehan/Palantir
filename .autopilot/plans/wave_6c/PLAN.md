# Wave 6C — Remaining CONSENSUS Features

**Date:** 2026-03-26
**Source:** `.brainstorm/CONSENSUS.md` (96 features total), cross-referenced against wave results and Python module list
**Status:** Planning phase — 62 features built, 34 remaining (see below)

---

## Built vs. Unbuilt Summary

### Already Built (62 features)
- **Wave 1 (23):** All bug fixes, security, DevEx, CI, property tests, RTB, UX quick fixes
- **Wave 2 (8):** sim_engine split, api_main split, autopilot tests, handler tests, verify_target fix, swarm autonomy, autonomy reset
- **Wave 3 (6):** roe_engine, audit_trail, kalman_fusion, hungarian_swarm, persistence/mission_store, websocket_auth
- **Wave 4 (6/12):** explainability, autonomy_policy (per-action matrix), confidence_gate, override_tracker, aar_engine, kill_chain_tracker
- **Wave 5 (10):** sim_controller, scenario_engine, weather_engine+jammer, uav_logistics, terrain_model, rbac, llm_sanitizer, report_generator, sensor_model upgrade, checkpoint
- **Wave 6A (6):** forward_sim, delta_compression, vectorized_detection, comms_sim, cep_model, dbscan_clustering
- **Wave 6B (6+1):** sensor_weighting, lost_link, uav_kinematics, corridor_detection, vision_fixes, config/settings

### NOT Built (34 features)
- **Wave 4 frontend (6):** W4-003, W4-005, W4-007, W4-009, W4-010, W4-011, W4-012
- **Wave 6 remaining (25 of 37):** W6-002, W6-003, W6-004, W6-005, W6-009, W6-010, W6-011, W6-014, W6-015, W6-016, W6-017, W6-018, W6-019, W6-021, W6-023, W6-024, W6-025, W6-026, W6-029, W6-030, W6-031, W6-032, W6-033, W6-035, W6-036

---

## Unbuilt Features — Detailed List

### Tier 1: Viable / Recommended for Wave 6C (16 features)

These are doable, high-value, and fit the demo/simulation scope.

---

#### 6C-001: Pre-Autonomy Briefing Screen (W4-003)
**Slug:** `autonomy_briefing`
**Priority:** P1 | **Effort:** S | **Complexity:** S
**Description:** Before AUTONOMOUS activation: modal showing autonomous actions, approval-required actions, reversion triggers, active ROE rules. Requires explicit "I understand" acknowledgment. Currently one mis-click removes human from lethal loop.
**New files:** None
**Modified files:** `src/frontend-react/src/panels/mission/AutonomyToggle.tsx`, new `src/frontend-react/src/panels/mission/AutonomyBriefingDialog.tsx`
**Dependencies:** W4-002 (autonomy_policy.py built) ✓
**Test approach:** React component test (Vitest), manual E2E

---

#### 6C-002: Global Alert Center + Strike Board Overlay (W4-005)
**Slug:** `global_alert_center`
**Priority:** P1 | **Effort:** M | **Complexity:** M
**Description:** Critical events visible from all tabs. TransitionToast system-wide (not ASSETS-only). Strike Board as floating overlay. PENDING nominations with countdown timer. ISR Queue one-click dispatch.
**New files:** `src/frontend-react/src/overlays/GlobalAlertCenter.tsx`, `src/frontend-react/src/overlays/FloatingStrikeBoard.tsx`
**Modified files:** `src/frontend-react/src/App.tsx`, `src/frontend-react/src/panels/mission/ISRQueue.tsx`
**Dependencies:** None
**Test approach:** Component tests, WebSocket mock

---

#### 6C-003: F2T2EA Kill Chain Progress Indicator (W4-007)
**Slug:** `kill_chain_ribbon`
**Priority:** P2 | **Effort:** S | **Complexity:** S
**Description:** Persistent ribbon showing 6 F2T2EA phases with target counts per phase. Click phase to filter target list. Color-coded by urgency. Backend `kill_chain_tracker.py` already exists.
**New files:** `src/frontend-react/src/overlays/KillChainRibbon.tsx`
**Modified files:** `src/frontend-react/src/App.tsx` (add ribbon), `src/frontend-react/src/store/SimulationStore.ts` (kill chain state)
**Dependencies:** kill_chain_tracker.py ✓
**Test approach:** Component test with mock state

---

#### 6C-004: WebSocket Connection Status Indicator (W4-009)
**Slug:** `ws_connection_status`
**Priority:** P2 | **Effort:** S | **Complexity:** S
**Description:** Connection quality indicator in header: green (<1s), yellow (1-5s), red (disconnected). Running average latency. Reconnection modal with retry count.
**New files:** `src/frontend-react/src/components/ConnectionStatus.tsx`
**Modified files:** `src/frontend-react/src/App.tsx`
**Dependencies:** None
**Test approach:** Component test with WebSocket mock

---

#### 6C-005: Command Palette (Cmd+K) (W4-010)
**Slug:** `command_palette`
**Priority:** P2 | **Effort:** M | **Complexity:** M
**Description:** Global Cmd+K / Ctrl+K triggers fuzzy command search. Commands: follow UAV, approve nomination, set autonomy, switch mode. Command history (recently used).
**New files:** `src/frontend-react/src/overlays/CommandPalette.tsx`
**Modified files:** `src/frontend-react/src/App.tsx` (keyboard handler)
**Dependencies:** None
**Test approach:** Component test with mock dispatch

---

#### 6C-006: Right-Click Context Menu on Globe (W4-011)
**Slug:** `context_menu_globe`
**Priority:** P2 | **Effort:** M | **Complexity:** M
**Description:** Right-click on Cesium entities: target menu (Follow/Paint/Verify/Nominate), drone menu (Set SEARCH/Assign/RTB). Execute WebSocket commands directly.
**New files:** `src/frontend-react/src/cesium/CesiumContextMenu.tsx`
**Modified files:** `src/frontend-react/src/cesium/CesiumContainer.tsx`
**Dependencies:** None
**Test approach:** Component test with Cesium mock

---

#### 6C-007: Swarm Health At-a-Glance Panel (W4-012)
**Slug:** `swarm_health_panel`
**Priority:** P2 | **Effort:** M | **Complexity:** M
**Description:** Compact grid/ring of drone indicators (color=mode, icon=sensor, border=fuel). Click opens full drone card. Addresses SA loss at 17+ UAVs.
**New files:** `src/frontend-react/src/panels/assets/SwarmHealthPanel.tsx`
**Modified files:** `src/frontend-react/src/panels/assets/AssetsTab.tsx`
**Dependencies:** None
**Test approach:** Component test with mock drone state

---

#### 6C-008: Frontend Testing Infrastructure (W6-005)
**Slug:** `frontend_tests`
**Priority:** P2 | **Effort:** L | **Complexity:** L
**Description:** Vitest + @testing-library/react setup. Playwright E2E for React: WS connect, Cesium renders, drone tracks update, HITL toast works.
**New files:** `src/frontend-react/src/tests/` directory, vitest config, playwright config
**Modified files:** `src/frontend-react/package.json`
**Dependencies:** None
**Test approach:** IS the feature

---

#### 6C-009: NVIS Night Operations Mode (W6-014)
**Slug:** `nvis_mode`
**Priority:** P3 | **Effort:** S | **Complexity:** S
**Description:** N key toggles NVIS mode. Green-dominant low-luminance CSS theme. All white backgrounds disabled.
**New files:** `src/frontend-react/src/styles/nvis.css`
**Modified files:** `src/frontend-react/src/App.tsx`
**Dependencies:** None
**Test approach:** Manual visual test

---

#### 6C-010: Color-Blind Accessible Mode (W6-015)
**Slug:** `colorblind_mode`
**Priority:** P3 | **Effort:** S | **Complexity:** S
**Description:** Shape+icon redundancy alongside color coding. "Accessibility Mode" toggle with blue/orange palette. WCAG AA contrast.
**New files:** `src/frontend-react/src/styles/accessibility.css`
**Modified files:** `src/frontend-react/src/App.tsx`
**Dependencies:** None
**Test approach:** Manual visual + contrast audit

---

#### 6C-011: Map Legend, Glossary, and Onboarding (W6-016)
**Slug:** `map_legend`
**Priority:** P3 | **Effort:** S | **Complexity:** S
**Description:** L key shows map legend overlay (all colors/icons explained). Glossary panel for military terms. Optional 5-step tooltip walkthrough.
**New files:** `src/frontend-react/src/overlays/MapLegend.tsx`, `src/frontend-react/src/overlays/GlossaryPanel.tsx`
**Modified files:** `src/frontend-react/src/App.tsx`
**Dependencies:** None
**Test approach:** Component tests

---

#### 6C-012: Batch Approve/Reject Nominations (W6-017)
**Slug:** `batch_approve`
**Priority:** P3 | **Effort:** S | **Complexity:** S
**Description:** [Approve All / Reject All / Approve by Type] toolbar on Strike Board. Batch confirmation with summary. Filter by target type.
**New files:** None
**Modified files:** `src/frontend-react/src/panels/mission/StrikeBoard.tsx`
**Dependencies:** None
**Test approach:** Component test with mock nominations

---

#### 6C-013: Target Kill Log and Engagement History (W6-018)
**Slug:** `kill_log`
**Priority:** P3 | **Effort:** S | **Complexity:** S
**Description:** "Engagement History" panel in ASSESS tab. Chronological list: target type, time, weapon, BDA confidence, outcome. Link to AI reasoning trace.
**New files:** `src/frontend-react/src/panels/assessment/EngagementHistory.tsx`
**Modified files:** `src/frontend-react/src/panels/assessment/AssessmentTab.tsx`
**Dependencies:** aar_engine.py ✓
**Test approach:** Component test with mock history data

---

#### 6C-014: Prometheus Metrics Endpoint (W6-023)
**Slug:** `prometheus_metrics`
**Priority:** P3 | **Effort:** S | **Complexity:** S
**Description:** `GET /metrics` Prometheus endpoint: tick duration, client count, detection events, HITL approvals. Frontend latency indicator in header.
**New files:** `src/python/metrics.py`
**Modified files:** `src/python/api_main.py` (add /metrics endpoint), `src/python/simulation_loop.py`
**Dependencies:** None
**Test approach:** Unit test endpoint + metric counters

---

#### 6C-015: TLS Support (W6-024)
**Slug:** `tls_support`
**Priority:** P3 | **Effort:** S | **Complexity:** S
**Description:** Uvicorn SSL config option. Allow HTTP on localhost, enforce HTTPS otherwise. Origin checking on WebSocket connections.
**New files:** None
**Modified files:** `src/python/config.py` (SSL settings), `src/python/api_main.py`
**Dependencies:** config.py ✓
**Test approach:** Unit test config loading

---

#### 6C-016: OpenAPI/AsyncAPI WebSocket Protocol Spec (W6-030)
**Slug:** `openapi_spec`
**Priority:** P3 | **Effort:** M | **Complexity:** M
**Description:** AsyncAPI spec documenting all WebSocket actions. Protocol version field on all messages. Published documentation.
**New files:** `docs/asyncapi.yaml`, `docs/websocket_protocol.md`
**Modified files:** `src/python/websocket_handlers.py` (add version field)
**Dependencies:** None
**Test approach:** Schema validation

---

### Tier 2: Deferred / Out of Scope for Wave 6C (18 features)

These are either XL effort (multi-month), require external hardware/data, or are aspirational research tracks not appropriate for a demo system milestone.

| ID | Slug | Reason Deferred |
|----|------|-----------------|
| W6-002 | `cot_bridge` | Requires Android TAK devices; no ATAK in demo env (CR-7) |
| W6-003 | `milsym` | P3, styling only; low demo value vs. effort |
| W6-004 | `hierarchical_ai` | P3, L effort; requires LangGraph rewrite of 9 agents |
| W6-009 | `mission_planning` | P3, L effort; UI requires drag-and-drop Cesium geometry editing |
| W6-010 | `pettingzoo_rl` | XL effort; multi-month RL research project (CR-4 caveat) |
| W6-011 | `mavlink_bridge` | XL effort; requires real hardware or simulation harness |
| W6-019 | `task_focus_mode` | P3, M effort; UX polish, not core capability |
| W6-021 | `plugin_system` | P3, L effort; architecture astronautics for demo scope |
| W6-025 | `behavioral_cloning` | XL effort; depends on PettingZoo RL env first |
| W6-026 | `federated_sensor` | L effort; requires per-drone calibration data not available |
| W6-029 | `zone_balancer_mpc` | M effort; MPC formulation requires control theory expertise |
| W6-031 | `benchmarks` | M effort; CI regression tracking setup, low immediate value |
| W6-032 | `bayesian_verification` | L effort; HIGH risk — replaces clean FSM, breaks 27 tests (CR-9) |
| W6-033 | `swarm_raft` | XL effort; distributed consensus for single-process demo (premature) |
| W6-035 | `gnn_data_assoc` | L effort; GNN data association requires track correlation infrastructure |
| W6-036 | `road_patrol` | L effort; requires road data sourcing (17 Feasibility risk) |

---

## Wave 6C Execution Plan

### Wave Groupings (Parallel Execution)

All Wave 6C features are **frontend-only or new backend modules** — no file conflicts between groups.

---

#### Wave 6C-Alpha (Parallel — All Frontend, No Conflicts)

| # | Feature | Slug | Effort | New Files | Modified Files |
|---|---------|------|--------|-----------|----------------|
| 1 | Pre-Autonomy Briefing | `autonomy_briefing` | S | `AutonomyBriefingDialog.tsx` | `AutonomyToggle.tsx` |
| 2 | Kill Chain Ribbon | `kill_chain_ribbon` | S | `KillChainRibbon.tsx` | `App.tsx`, `SimulationStore.ts` |
| 3 | WS Connection Status | `ws_connection_status` | S | `ConnectionStatus.tsx` | `App.tsx` |
| 4 | NVIS Night Mode | `nvis_mode` | S | `nvis.css` | `App.tsx` |
| 5 | Color-Blind Mode | `colorblind_mode` | S | `accessibility.css` | `App.tsx` |
| 6 | Map Legend + Glossary | `map_legend` | S | `MapLegend.tsx`, `GlossaryPanel.tsx` | `App.tsx` |
| 7 | Batch Approve/Reject | `batch_approve` | S | None | `StrikeBoard.tsx` |
| 8 | Engagement History | `kill_log` | S | `EngagementHistory.tsx` | `AssessmentTab.tsx` |
| 9 | Prometheus Metrics | `prometheus_metrics` | S | `src/python/metrics.py` | `api_main.py` |
| 10 | TLS Support | `tls_support` | S | None | `config.py`, `api_main.py` |

**Parallelism:** All 10 can run simultaneously — no file conflicts.

---

#### Wave 6C-Beta (Parallel — Medium Features, Some Frontend Overlap)

| # | Feature | Slug | Effort | New Files | Modified Files |
|---|---------|------|--------|-----------|----------------|
| 11 | Command Palette | `command_palette` | M | `CommandPalette.tsx` | `App.tsx` |
| 12 | Right-Click Globe Menu | `context_menu_globe` | M | `CesiumContextMenu.tsx` | `CesiumContainer.tsx` |
| 13 | Swarm Health Panel | `swarm_health_panel` | M | `SwarmHealthPanel.tsx` | `AssetsTab.tsx` |
| 14 | Global Alert Center | `global_alert_center` | M | `GlobalAlertCenter.tsx`, `FloatingStrikeBoard.tsx` | `App.tsx`, `ISRQueue.tsx` |
| 15 | OpenAPI Spec | `openapi_spec` | M | `docs/asyncapi.yaml` | `websocket_handlers.py` |

**Parallelism:** All 5 can run simultaneously — different files.

---

#### Wave 6C-Gamma (Sequential — Large Feature)

| # | Feature | Slug | Effort | New Files | Modified Files |
|---|---------|------|--------|-----------|----------------|
| 16 | Frontend Testing | `frontend_tests` | L | vitest.config.ts, playwright.config.ts, test files | `package.json` |

**Note:** This should run after 6C-Alpha and 6C-Beta so tests cover those new components.

---

## File Conflict Analysis

| Conflict | Features | Resolution |
|----------|---------|------------|
| `App.tsx` | 6C-001 through 6C-009 | Safe — each adds independent hooks/renders, no logic overlap |
| `api_main.py` | 6C-014 (metrics) + 6C-015 (TLS) | Serialize 6C-015 after 6C-014, or run carefully — different sections |
| `config.py` | 6C-015 (TLS settings) | No conflict with other features |
| `AssessmentTab.tsx` | 6C-013 (kill log) only | No conflict |

---

## Dependency Map

```
All Wave 6C features are independent — no inter-feature dependencies.

6C-001 (AutonomyBriefing) → uses autonomy_policy.py (already built ✓)
6C-003 (KillChainRibbon) → uses kill_chain_tracker.py (already built ✓)
6C-013 (EngagementHistory) → uses aar_engine.py (already built ✓)
6C-016 (OpenAPI Spec) → documents existing websocket_handlers.py (already built ✓)
6C-014 (Prometheus) → reads from existing simulation_loop.py (already built ✓)

Wave 6C-Gamma:
6C-008 (FrontendTests) → best after 6C-Alpha + 6C-Beta complete (more to test)
```

---

## Test Strategy Per Feature

| Feature | Test Type | Test Files |
|---------|-----------|-----------|
| `autonomy_briefing` | React component (Vitest) | `tests/AutonomyBriefingDialog.test.tsx` |
| `global_alert_center` | React component (Vitest) | `tests/GlobalAlertCenter.test.tsx` |
| `kill_chain_ribbon` | React component (Vitest) | `tests/KillChainRibbon.test.tsx` |
| `ws_connection_status` | React component (Vitest) | `tests/ConnectionStatus.test.tsx` |
| `command_palette` | React component (Vitest) | `tests/CommandPalette.test.tsx` |
| `context_menu_globe` | React component (Vitest) | `tests/CesiumContextMenu.test.tsx` |
| `swarm_health_panel` | React component (Vitest) | `tests/SwarmHealthPanel.test.tsx` |
| `nvis_mode` | Manual visual | N/A |
| `colorblind_mode` | Manual visual | N/A |
| `map_legend` | React component (Vitest) | `tests/MapLegend.test.tsx` |
| `batch_approve` | React component (Vitest) | `tests/StrikeBoard.test.tsx` |
| `kill_log` | React component (Vitest) | `tests/EngagementHistory.test.tsx` |
| `prometheus_metrics` | Python unit test | `tests/test_metrics.py` |
| `tls_support` | Python unit test | `tests/test_tls_config.py` |
| `openapi_spec` | Schema validation | `tests/test_asyncapi_schema.py` |
| `frontend_tests` | Is the feature | vitest + playwright |

---

## Summary

| Wave | Features | Estimated Effort | Notes |
|------|----------|-----------------|-------|
| 6C-Alpha | 10 | ~1-2 person-days | All S, fully parallel |
| 6C-Beta | 5 | ~1.5 person-days | M features, fully parallel |
| 6C-Gamma | 1 | ~2 person-days | L, sequential after Alpha+Beta |
| **6C Total** | **16** | **~4-5 person-days** | |
| Deferred | 18 | N/A | XL, research-grade, or external-hardware |

**Recommended execution order:**
```
Wave 6C-Alpha (10 parallel builders, S features, ~0.5 day wall-clock)
  ↓
Wave 6C-Beta (5 parallel builders, M features, ~0.5 day wall-clock)
  ↓
Wave 6C-Gamma (frontend testing, ~1 day wall-clock)
```
