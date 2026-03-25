# Implement Three NotImplementedError Agents (W1-003)

## Summary
Implement `_generate_response()` in battlespace_manager, pattern_analyzer, and synthesis_query_agent so they return useful output instead of crashing.

## Files to Modify
- `src/python/agents/synthesis_query_agent.py` — Implement `_generate_response()` to query sim state and format a SITREP
- `src/python/agents/pattern_analyzer.py` — Implement `_generate_response()` to analyze target activity patterns using existing battlespace assessment
- `src/python/agents/battlespace_manager.py` — Implement `_generate_response()` to generate mission path data from existing modules

## Files to Create
- `src/python/tests/test_synthesis_query_agent.py` — Tests for SITREP generation
- `src/python/tests/test_pattern_analyzer_impl.py` — Tests for pattern analysis (avoid name collision with existing test file)
- `src/python/tests/test_battlespace_manager_impl.py` — Tests for battlespace manager

## Test Plan (TDD — write these FIRST)
1. `test_synthesis_generates_sitrep_from_state` — Returns formatted SITREP string with target/drone counts
2. `test_synthesis_handles_empty_state` — Graceful output when no targets/drones
3. `test_synthesis_includes_threat_summary` — SITREP contains threat-level info
4. `test_pattern_analyzer_returns_patterns` — Returns pattern dict with activity data
5. `test_pattern_analyzer_handles_no_targets` — Graceful with empty target list
6. `test_pattern_analyzer_uses_assessment` — Calls battlespace_assessment functions
7. `test_battlespace_manager_returns_path` — Returns mission path data structure
8. `test_battlespace_manager_handles_no_zones` — Graceful with empty zone data
9. `test_no_agent_raises_not_implemented` — None of the 3 agents raise NotImplementedError

## Implementation Steps
1. In `synthesis_query_agent.py`: implement `_generate_response()` to pull drone count, target count, threat clusters, verification status from sim state; format as structured SITREP text
2. In `pattern_analyzer.py`: implement `_generate_response()` to call `identify_threat_clusters()` and `detect_movement_corridors()` from battlespace_assessment; return structured pattern analysis
3. In `battlespace_manager.py`: implement `_generate_response()` to generate zone-based mission data using existing `calculate_zone_threat_scores()` and zone geometry

## Verification
- [ ] SITREP button in UI returns formatted text (no crash)
- [ ] Each agent callable with `_generate_response()` without exception
- [ ] All new + existing tests pass

## Rollback
- Revert the three agent files to their NotImplementedError state
