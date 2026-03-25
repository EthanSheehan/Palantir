# 01 — Code Archaeology Report

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 4 |
| HIGH | 6 |
| MEDIUM | 7 |
| LOW | 11 |

## CRITICAL Findings

| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| 1 | `agents/battlespace_manager.py:167` | NotImplementedError | `_generate_response()` raises NotImplementedError — `generate_mission_path()` always crashes |
| 2 | `agents/pattern_analyzer.py:79` | NotImplementedError | `_generate_response()` raises NotImplementedError — `analyze_patterns()` always crashes |
| 3 | `agents/synthesis_query_agent.py:117` | NotImplementedError | `_generate_response()` raises NotImplementedError — `generate_sitrep()` always crashes |
| 5 | `api_main.py:275` | BUG | `_find_nearest_available_uav()` filters `"SCANNING"` (invalid) instead of `"SEARCH"` — autopilot never selects SEARCH-mode drones |

## HIGH Findings

| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| 4 | `agents/ai_tasking_manager.py:61` | STUB | `_generate_response()` raises NotImplementedError, but heuristic fallback exists and is used |
| 6 | `api_main.py:323` | DEAD CODE | `elif e.mode == "DESTROYED"` unreachable — `continue` guard on line 307 prevents reaching it; `enemy_intercept_dispatched` grows unboundedly |
| 9 | `pipeline.py:81` | PLACEHOLDER | `hitl_approve()` uses blocking `input()` — would freeze async server if called |
| 11 | `vision/video_simulator.py:147-151` | STUB | `TrackingScenario.update_drone()` is `pass` — drone never chases targets |
| 15 | `vision/vision_processor.py:27-34` | PLACEHOLDER | Hardcoded Bristol UK coordinates instead of real telemetry |
| 27 | `hooks/useSensorCanvas.ts:468-504` | STUB | SIGINT sensor view renders placeholder banner, not functional |
| 28 | `test_data_synthesizer.py` | DEAD | References non-existent `/ingest` endpoint |

## MEDIUM Findings

| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| 8 | `api_main.py:427,498,502,507` | SWALLOW | `except ValueError: pass` silences COA authorization failures |
| 12 | `vision/video_simulator.py:174,184` | HARDCODED | URL hardcoded to `ws://localhost:8000/ws`, speed `15.0 m/s mock` |
| 18 | `sim_engine.py:387` | PLACEHOLDER | RTB mode: "drift slowly for now" — no actual RTB destination logic |
| 22 | `agents/performance_auditor.py:56-57` | PLACEHOLDER | In-memory stores with comment "replace with persistent storage" |
| 23 | `mission_data/asset_registry.py:12` | PLACEHOLDER | Static hardcoded list with "Replace with DB queries" |
| 24 | `mission_data/historical_activity.py:27` | PLACEHOLDER | Hardcoded 90-day log with "Replace with DB queries" |
| 25 | `api_main.py:514` | HARDCODED | CORS origins hardcoded to localhost:3000 |
| 26 | `api_main.py:867` | PLACEHOLDER | retask_sensors uses empty asset list — no live sensor registry |

## LOW Findings

| # | File:Line | Type | Description |
|---|-----------|------|-------------|
| 7 | `api_main.py:83` | SWALLOW | `_send_error()` silently swallows disconnects |
| 10 | `vision/video_simulator.py:121-122` | EMPTY | `MissionScenario.update_drone()` is `pass` — intentional base class |
| 13 | `vision/video_simulator.py:198` | INCONSISTENT | `_drone_mode = "SCANNING"` not a valid mode |
| 14 | `vision/video_simulator.py:408` | PASS | Intentional branch skip |
| 16 | `vision/dashboard_connector.py:111-113` | TEST ARTIFACT | Leftover `__main__` mock test |
| 17 | `event_logger.py:46,70,83` | SWALLOW | Intentional drops on queue full and CancelledError |
| 19 | `sim_engine.py:393` | STALE | Comment references "VIEWING" — not a valid mode |
| 20 | `sensor_model.py:167` | UNUSED | `altitude_penalty` documented but not applied |
| 21 | `isr_priority.py:122` | PLACEHOLDER | `assessment_result` param "reserved for future use" |

## Autopilot-Specific Issues

| ID | File:Line | Issue |
|----|-----------|-------|
| A | `api_main.py:275` | **CRITICAL BUG** — `"SCANNING"` vs `"SEARCH"` breaks drone dispatch |
| B | `api_main.py:323` | **DEAD BRANCH** — destroyed enemy cleanup unreachable, set grows unboundedly |
| C | `api_main.py:282-442` | **DESIGN** — sequential `asyncio.sleep()` per entry: 14s delay per nomination |
| D | `pipeline.py:81` | **BLOCKING** — legacy `input()` in hitl_approve() |
