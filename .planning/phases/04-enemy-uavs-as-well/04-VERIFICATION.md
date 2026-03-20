---
phase: 04-enemy-uavs-as-well
verified: 2026-03-20T10:00:00Z
status: human_needed
score: 13/13 must-haves verified
human_verification:
  - test: "Run ./palantir.sh --demo and open http://localhost:3000. On the Cesium globe, confirm 3 red entities with ENM-0/ENM-1/ENM-2 labels are visible."
    expected: "Three red point entities with mode-colored labels appear on the globe, separate from friendly blue drones."
    why_human: "Cesium rendering cannot be verified programmatically — requires visual confirmation in a live browser."
  - test: "Click the ENEMIES tab. Confirm an 'Airborne Threats' section appears with EnemyUAVCard entries showing mode, confidence percentage, sensor count, and a JAMMING badge on the jamming drone."
    expected: "Airborne Threats section renders with at least one card; the JAMMING drone card shows an amber JAMMING badge."
    why_human: "React component rendering and Blueprint UI appearance requires visual inspection."
  - test: "In demo mode, watch an enemy UAV card until confidence exceeds 50%. Confirm the entity on the globe changes direction and the mode label switches to EVADING."
    expected: "Enemy UAV transitions to EVADING, moves in a new random direction, and the Cesium label color/text reflects the new mode."
    why_human: "Mode transition timing and visual state change on Cesium entities requires live observation."
  - test: "In demo mode, wait for demo autopilot to auto-dispatch a friendly UAV to intercept a detected enemy. Watch until the intercepting UAV reaches the enemy. Confirm the enemy turns gray (DESTROYED) and stops moving."
    expected: "Intercept kill sequence completes: friendly UAV approaches, dwells 3s, enemy transitions to DESTROYED with no further movement."
    why_human: "Kill mechanic timing and visual feedback on Cesium globe requires live observation."
---

# Phase 04: Enemy UAVs Verification Report

**Phase Goal:** Add adversary UAVs to the simulation. Enemy drones with configurable behaviors (recon, attack, jamming), detection by friendly sensors, threat classification, and evasion/intercept mechanics.
**Verified:** 2026-03-20
**Status:** human_needed — all automated checks pass; 4 items require visual confirmation in a live browser.
**Re-verification:** No — initial verification.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | EnemyUAV entities exist as a separate class from Target and UAV | VERIFIED | `class EnemyUAV` at sim_engine.py:389; `self.enemy_uavs: List[EnemyUAV] = []` at :556; no EnemyUAV in sim.targets list (TestSeparation passes) |
| 2 | Friendly sensors detect enemy UAVs using the existing evaluate_detection() pipeline | VERIFIED | sim_engine.py:916-925 calls `evaluate_detection(..., target_type="ENEMY_UAV", emitting=e.is_jamming)` inside section 10 loop |
| 3 | Enemy UAVs move with fixed-wing physics (reusing _turn_toward pattern) | VERIFIED | `EnemyUAV._turn_toward()` defined in sim_engine.py; `e.update(dt_sec, self.bounds)` called at sim_engine.py:901; TestEnemyUAVMovement all pass |
| 4 | Enemy UAVs appear in get_state() under a separate 'enemy_uavs' key | VERIFIED | sim_engine.py:1399-1412 builds `"enemy_uavs": [...]` list in get_state(); TestGetState passes |
| 5 | Enemy UAVs never appear in sim.targets list | VERIFIED | TestSeparation::test_enemy_uavs_not_in_targets passes; `_find_target(1000)` returns None confirmed by test |
| 6 | JAMMING enemy UAVs are detectable at longer range by SIGINT sensors | VERIFIED | `emitting=e.is_jamming` at sim_engine.py:925; TestJammingDetection::test_jamming_enemy_detected_by_sigint passes; `"ENEMY_UAV": 0.1` in sensor_model.py RCS_TABLE at line 67 |
| 7 | 10Hz loop maintained with up to 8 enemy UAVs | VERIFIED | TestPerformance::test_10hz_with_8_enemies passes (100 ticks in 3.76s wall for 31-test file) |
| 8 | EnemyUAV TypeScript interface exists with all broadcast fields | VERIFIED | `export interface EnemyUAV` at types.ts:48; all fields (id, lat, lon, mode, behavior, heading_deg, detected, fused_confidence, sensor_count, is_jamming) present |
| 9 | Zustand store receives and stores enemyUavs from WebSocket payload | VERIFIED | SimulationStore.ts:132 sets `enemyUavs: data.enemy_uavs \|\| []`; store field initialized at :86 |
| 10 | Cesium renders red-labeled enemy UAV entities on the globe | VERIFIED (automated) | useCesiumEnemyUAVs.ts exists and exports `useCesiumEnemyUAVs`; CesiumContainer.tsx:33 calls `useCesiumEnemyUAVs(viewerRef)`; ENEMY_MODE_STYLES wired in; visual confirmation needed |
| 11 | ENEMIES tab shows EnemyUAVCard for each detected enemy UAV | VERIFIED (automated) | EnemiesTab.tsx:58-64 renders `Airborne Threats` section with `detectedEnemyUavs.map(e => <EnemyUAVCard ...>)`; visual confirmation needed |
| 12 | Friendly UAV in INTERCEPT mode can kill an enemy UAV at close range | VERIFIED | `command_intercept_enemy()` at sim_engine.py:683; `_update_enemy_intercept()` at :946; TestInterceptKill::test_kill_at_close_range passes (31 ticks) |
| 13 | Enemy UAVs evade when detected with confidence > 0.5, with hysteresis cooldown | VERIFIED | sim_engine.py:475-484 implements evasion trigger at fused_confidence > 0.5, 15s cooldown, _original_mode restore; TestEvasion all 4 tests pass |

**Score:** 13/13 truths verified (4 require human visual confirmation for full acceptance)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/python/sim_engine.py` | EnemyUAV class and detection loop | VERIFIED | `class EnemyUAV` at :389; detection loop section 10 at :903-944; all required methods present |
| `src/python/sensor_model.py` | RCS entry for ENEMY_UAV | VERIFIED | `"ENEMY_UAV": 0.1` at line 67 in RCS_TABLE |
| `src/python/tests/test_enemy_uavs.py` | TDD tests for all enemy UAV behaviors | VERIFIED | 31 tests across 9 classes: TestEnemyUAVSpawn, TestEnemyUAVMovement, TestSeparation, TestGetState, TestEnemyUAVDetection, TestJammingDetection, TestEvasion, TestInterceptKill, TestTheaterConfig, TestPerformance — all pass |
| `src/frontend-react/src/store/types.ts` | EnemyUAV interface | VERIFIED | `export interface EnemyUAV` at :48; `enemy_uavs?` in SimStatePayload at :132 |
| `src/frontend-react/src/cesium/useCesiumEnemyUAVs.ts` | Cesium hook for enemy UAV entities | VERIFIED | File exists; `export function useCesiumEnemyUAVs` confirmed; useSimStore(state => state.enemyUavs) wired |
| `src/frontend-react/src/panels/enemies/EnemyUAVCard.tsx` | Blueprint card for enemy UAV in sidebar | VERIFIED | File exists; `export function EnemyUAVCard` confirmed; renders fused_confidence, sensor_count, is_jamming badge |
| `src/python/sim_engine.py` | Intercept kill mechanic and evasion behavior | VERIFIED | `def command_intercept_enemy` at :683; `evasion_cooldown` at :405; `_original_mode` at :407; `_update_enemy_intercept` at :946 |
| `theaters/romania.yaml` | enemy_uavs YAML config section | VERIFIED | Lines 56-62: 2 RECON (400 km/h) + 1 JAMMING (0 km/h) |
| `src/python/api_main.py` | intercept_enemy WS action and demo autopilot enemy handling | VERIFIED | `intercept_enemy` action at :781-783; `command_intercept_enemy` in demo_autopilot at :308; `enemy_intercept_dispatched` set at :293 |
| `src/python/theater_loader.py` | EnemyUAVUnitConfig and EnemyUAVConfig dataclasses | VERIFIED | Both dataclasses at :72-80; `_parse_enemy_uavs()` at :188; `TheaterConfig.enemy_uavs` optional field at :92 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| sim_engine.py | sensor_model.py | `evaluate_detection(..., target_type="ENEMY_UAV")` | WIRED | sim_engine.py:921 calls with `target_type="ENEMY_UAV"` |
| sim_engine.py | sensor_fusion.py | `fuse_detections(contributions)` in enemy UAV loop | WIRED | sim_engine.py:937 calls `fuse_detections(contributions)` inside section 10 |
| sim_engine.py | theaters/romania.yaml | `enemy_uavs` config section read during initialize | WIRED | sim_engine.py:616 reads `self.theater.enemy_uavs`; romania.yaml has the section |
| api_main.py | sim_engine.py | `command_intercept_enemy()` from WS action | WIRED | api_main.py:782 calls `sim.command_intercept_enemy(...)` |
| api_main.py | sim_engine.py | `command_intercept_enemy()` from demo_autopilot | WIRED | api_main.py:308 calls `sim.command_intercept_enemy(nearest.id, e.id)` |
| SimulationStore.ts | types.ts | EnemyUAV type import | WIRED | SimulationStore.ts:2 imports EnemyUAV from `./types` |
| useCesiumEnemyUAVs.ts | SimulationStore.ts | `useSimStore(state => state.enemyUavs)` | WIRED | useCesiumEnemyUAVs.ts uses `useSimStore` to subscribe to enemyUavs |
| CesiumContainer.tsx | useCesiumEnemyUAVs.ts | `useCesiumEnemyUAVs(viewerRef)` call | WIRED | CesiumContainer.tsx:14 imports and :33 calls the hook |
| EnemiesTab.tsx | EnemyUAVCard.tsx | EnemyUAVCard rendered per detected enemy | WIRED | EnemiesTab.tsx:5 imports; :64 renders `<EnemyUAVCard key={e.id} enemyUav={e} />` |

---

## Requirements Coverage

The plans declared requirement IDs EUAV-01 through EUAV-13. These IDs do **not** appear in `.planning/REQUIREMENTS.md` — that file uses FR-1 through NFR-4 format. The EUAV IDs are internal phase-level tracking only.

Mapping EUAV IDs to plans and verification status:

| Requirement | Source Plan | Description (inferred from plan content) | Status |
|-------------|------------|------------------------------------------|--------|
| EUAV-01 | Plan 01 | EnemyUAV class with modes | SATISFIED |
| EUAV-02 | Plan 01 | Fixed-wing physics for enemy UAVs | SATISFIED |
| EUAV-03 | Plan 03 | Evasion behavior with hysteresis | SATISFIED |
| EUAV-04 | Plan 03 | Intercept kill mechanic (dwell-based) | SATISFIED |
| EUAV-05 | Plan 01 | Separate enemy_uavs list from targets | SATISFIED |
| EUAV-06 | Plan 01 | Detection via evaluate_detection pipeline | SATISFIED |
| EUAV-07 | Plan 01 | JAMMING mode emits for SIGINT detection | SATISFIED |
| EUAV-08 | Plan 01 | 10Hz loop maintained with 8 enemy UAVs | SATISFIED |
| EUAV-09 | Plan 03 | Theater YAML configures enemy UAV count/behaviors | SATISFIED |
| EUAV-10 | Plan 02 | EnemyUAV TypeScript interface | SATISFIED |
| EUAV-11 | Plan 02 | Cesium renders red ENM-N entities | SATISFIED (needs human visual) |
| EUAV-12 | Plan 02 | EnemyUAVCard in ENEMIES tab | SATISFIED (needs human visual) |
| EUAV-13 | Plan 03 | Demo autopilot auto-intercepts at confidence > 0.7 | SATISFIED |

**Note:** EUAV IDs are absent from `.planning/REQUIREMENTS.md`. No orphaned requirements were found — all 13 EUAV IDs were claimed by the 3 plans and all are verified against the codebase.

---

## Anti-Patterns Found

No blockers or warnings found.

- No TODO/FIXME/PLACEHOLDER comments in any enemy UAV code paths.
- No empty implementations (`return null`, `return {}`, stub handlers).
- No console.log-only handlers.
- EVADING stub from Plan 01 was fully replaced by Plan 03 (random heading changes at 1.5x speed — not a placeholder loiter).

---

## Human Verification Required

### 1. Enemy UAV Entities on Cesium Globe

**Test:** Run `./palantir.sh --demo` and open `http://localhost:3000`. Look at the Cesium globe.
**Expected:** 3 red point entities with labels "ENM-0", "ENM-1", "ENM-2" appear on the globe, distinct from the blue friendly drone labels.
**Why human:** Cesium WebGL rendering cannot be verified programmatically.

### 2. EnemyUAVCard in ENEMIES Tab

**Test:** Click the ENEMIES tab in the sidebar. Look for an "Airborne Threats" section below ground targets.
**Expected:** Cards appear for detected enemy UAVs showing: mode badge (red/amber colored), confidence percentage, sensor count. The JAMMING drone should show an amber "JAMMING" tag.
**Why human:** React component rendering and Blueprint UI requires visual inspection.

### 3. Evasion Behavior — Mode Transition

**Test:** In demo mode, watch an enemy UAV card in the sidebar until the confidence indicator climbs above 50%. Observe the entity on the Cesium globe simultaneously.
**Expected:** The enemy UAV mode label changes to "EVADING" (purple), the entity changes heading and moves in a new direction, and the EnemyUAVCard badge updates to EVADING color.
**Why human:** Mode transition timing and Cesium label color update requires live observation.

### 4. Intercept Kill Sequence

**Test:** In demo mode, wait for demo autopilot to dispatch an intercept (a friendly UAV should switch to INTERCEPT mode targeting an enemy). Watch the intercepting UAV close in on the enemy UAV on the globe.
**Expected:** After the friendly UAV reaches close range and holds for ~3 seconds, the enemy UAV transitions to DESTROYED (gray label, stops moving). The friendly UAV then switches back to SEARCH mode.
**Why human:** Kill mechanic timing and Cesium entity state changes require live observation.

---

## Test Results Summary

```
src/python/tests/test_enemy_uavs.py: 31 passed
src/python/tests/ (full suite): 387 passed, 68 warnings
TypeScript: compiles clean (confirmed by Plan 02 SUMMARY)
```

---

_Verified: 2026-03-20_
_Verifier: Claude (gsd-verifier)_
