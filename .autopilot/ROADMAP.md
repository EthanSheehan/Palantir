# Wave 1 Execution Roadmap

**Total features:** 24 (W1-001 through W1-023 + W1-013b verify_target bypass fix)
**Total estimated new LOC:** ~2,800 (production) + ~1,800 (tests) = ~4,600
**Estimated new test count:** ~85 tests across all features

---

## Builder Group Assignments

All Wave 1 features are independent — no inter-feature dependencies. Grouped by domain for builder efficiency.

### Group A: Critical Bug Fixes (Builder 1)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `fix_scanning_bug.md` | W1-001: Fix SCANNING→SEARCH | 3 | 30 |
| `fix_dead_enemy_cleanup.md` | W1-002: Fix dead enemy cleanup | 3 | 40 |
| `fix_silent_valueerror.md` | W1-004: Fix silent ValueError | 3 | 30 |
| `delete_pipeline_dead_code.md` | W1-005: Delete pipeline.py | 2 | -130 (deletion) |
| `fix_tactical_assistant_memory.md` | W1-007: Fix TacticalAssistant memory | 3 | 30 |
| **Subtotal** | **5 features** | **14** | **~0 net** |

### Group B: Security Hardening (Builder 2)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `websocket_size_guard.md` | W1-011: WebSocket size guard | 3 | 20 |
| `fix_hitl_replay.md` | W1-012: Fix HITL replay attack | 4 | 20 |
| `input_validation.md` | W1-013: Input validation | 12 | 120 |
| `autopilot_circuit_breaker.md` | W1-014: Circuit breaker | 5 | 80 |
| `fix_verify_target_bypass.md` | W1-013b: Fix verify_target bypass | 3 | 30 |
| **Subtotal** | **5 features** | **27** | **~270** |

### Group C: Performance Optimization (Builder 3)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `cache_get_state.md` | W1-008: Cache get_state() | 3 | 20 |
| `dict_entity_lookups.md` | W1-009: Dict entity lookups | 5 | 100 |
| `isr_queue_async_and_event_logger.md` | W1-010: Async ISR + event logger | 4 | 50 |
| **Subtotal** | **3 features** | **12** | **~170** |

### Group D: Agent Implementation (Builder 4)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `implement_agents.md` | W1-003: Implement 3 agents | 9 | 200 |
| **Subtotal** | **1 feature** | **9** | **~200** |

### Group E: DevEx & CI (Builder 5)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `pyproject_toml.md` | W1-015: pyproject.toml | 2 | 80 |
| `pre_commit_hooks.md` | W1-016: Pre-commit hooks | 2 | 40 |
| `github_actions_ci.md` | W1-017: GitHub Actions CI | 3 | 200 |
| `makefile.md` | W1-018: Makefile | 2 | 60 |
| **Subtotal** | **4 features** | **9** | **~380** |

### Group F: Testing Infrastructure (Builder 6)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `hypothesis_property_tests.md` | W1-019: Hypothesis tests | 10 | 250 |
| **Subtotal** | **1 feature** | **10** | **~250** |

### Group G: Library Upgrades (Builder 7)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `add_shapely_turf.md` | W1-020: Shapely + turf.js | 4 | 100 |
| `kdtree_clustering.md` | W1-021: KD-Tree clustering | 5 | 60 |
| `fix_rtb_mode.md` | W1-022: Fix RTB navigation | 4 | 60 |
| **Subtotal** | **3 features** | **13** | **~220** |

### Group H: Frontend UX (Builder 8)
| Plan File | Feature | Est. Tests | Est. LOC |
|-----------|---------|-----------|---------|
| `fix_cesium_memory_leak.md` | W1-006: Cesium memory leak | 2 | 30 |
| `ux_quick_fixes.md` | W1-023: Dead buttons + shortcuts | 5 | 150 |
| **Subtotal** | **2 features** | **7** | **~180** |

---

## Execution Order

All groups execute in parallel. No group depends on another.

```
Time →
  Group A (Bug Fixes)      ████  (~0.5d)
  Group B (Security)        ██████████  (~1d)
  Group C (Performance)     ██████  (~0.5d)
  Group D (Agents)          ████████████  (~1.5d)
  Group E (DevEx/CI)        ██████████████  (~1.5d)
  Group F (Property Tests)  ██████  (~0.5d)
  Group G (Libraries)       ████████  (~1d)
  Group H (Frontend UX)     ██████  (~0.5d)
```

**Wall-clock with 4+ builders: ~1.5 days**
**Wall-clock with 2 builders: ~3 days**

---

## Success Criteria (Wave 1 Complete)

- [ ] `./grid_sentinel.sh --demo` runs full F2T2EA cycle — drones dispatch to targets
- [ ] All agents callable without NotImplementedError
- [ ] No silent exception swallowing
- [ ] No memory leaks in 30-minute demo
- [ ] WebSocket input validated on all actions
- [ ] HITL replay attack closed
- [ ] Demo autopilot has safety circuit breaker
- [ ] 80%+ test coverage
- [ ] CI pipeline active on GitHub
- [ ] Property-based tests validate critical invariants
- [ ] O(1) entity lookups, cached get_state()
- [ ] RTB mode actually navigates home
- [ ] Keyboard shortcuts operational
- [ ] All 475+ existing tests pass + ~85 new tests

---

## Plan File Index

| # | Slug | Feature ID | Priority |
|---|------|-----------|----------|
| 1 | `fix_scanning_bug.md` | W1-001 | P0 |
| 2 | `fix_dead_enemy_cleanup.md` | W1-002 | P0 |
| 3 | `implement_agents.md` | W1-003 | P0 |
| 4 | `fix_silent_valueerror.md` | W1-004 | P0 |
| 5 | `delete_pipeline_dead_code.md` | W1-005 | P1 |
| 6 | `fix_cesium_memory_leak.md` | W1-006 | P0 |
| 7 | `fix_tactical_assistant_memory.md` | W1-007 | P0 |
| 8 | `cache_get_state.md` | W1-008 | P0 |
| 9 | `dict_entity_lookups.md` | W1-009 | P0 |
| 10 | `isr_queue_async_and_event_logger.md` | W1-010 | P1 |
| 11 | `websocket_size_guard.md` | W1-011 | P0 |
| 12 | `fix_hitl_replay.md` | W1-012 | P0 |
| 13 | `input_validation.md` | W1-013 | P0 |
| 14 | `autopilot_circuit_breaker.md` | W1-014 | P0 |
| 15 | `pyproject_toml.md` | W1-015 | P0 |
| 16 | `pre_commit_hooks.md` | W1-016 | P0 |
| 17 | `github_actions_ci.md` | W1-017 | P1 |
| 18 | `makefile.md` | W1-018 | P1 |
| 19 | `hypothesis_property_tests.md` | W1-019 | P1 |
| 20 | `add_shapely_turf.md` | W1-020 | P1 |
| 21 | `kdtree_clustering.md` | W1-021 | P1 |
| 22 | `fix_rtb_mode.md` | W1-022 | P1 |
| 23 | `ux_quick_fixes.md` | W1-023 | P1 |
| 24 | `fix_verify_target_bypass.md` | W1-013b | P0 |
