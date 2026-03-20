---
phase: 06-information-feeds-event-log
plan: "01"
subsystem: backend-feed-multiplexing
tags: [intel-feed, event-log, websocket, subscription, tdd]
dependency_graph:
  requires: []
  provides: [intel-feed-router, subscription-filtered-broadcast, command-feed, intel-feed, log-rotation]
  affects: [api_main, event_logger]
tech_stack:
  added: [intel_feed.py]
  patterns: [subscription-filtered broadcast, enriched event deque, TDD red-green]
key_files:
  created:
    - src/python/intel_feed.py
    - src/python/tests/test_feeds.py
  modified:
    - src/python/event_logger.py
    - src/python/api_main.py
decisions:
  - "IntelFeedRouter stores enriched events in collections.deque(maxlen=200) — fixed cap prevents memory growth"
  - "broadcast() feed= param added — legacy clients (no subscriptions key) receive all broadcasts unchanged"
  - "All log_event(command) calls replaced with intel_router.emit — 15 emit calls total in api_main"
  - "rotate_logs called at startup lifespan — prevents unbounded log accumulation"
  - "_prev_target_states dict initialized at module level — tracks state across simulation ticks"
metrics:
  duration: 260s
  completed: "2026-03-20"
  tasks_completed: 2
  files_changed: 4
---

# Phase 06 Plan 01: Information Feeds Backend Summary

Backend feed multiplexing layer with IntelFeedRouter, subscription-filtered broadcast, COMMAND_FEED/INTEL_FEED event wiring, and log rotation.

## What Was Built

- `intel_feed.py` — `IntelFeedRouter` class with `emit()` (enriches, logs, broadcasts) and `get_history()` (capped deque, filterable by feed type), plus `_client_subscribed()` helper for subscription-based broadcast filtering
- `event_logger.py` — added `rotate_logs(max_days)` that deletes oldest JSONL files beyond the retention window
- `api_main.py` — wired `IntelFeedRouter` as `intel_router`, added `feed=` param to `broadcast()`, replaced all 15 `log_event()` command/engagement/nomination/transition calls with `await intel_router.emit()`, added `subscribe` and `subscribe_sensor_feed` WebSocket actions with history catch-up, added `_prev_target_states` dict + INTEL_FEED emission for automatic target state transitions in `simulation_loop()`
- `tests/test_feeds.py` — 12 tests: 9 unit (TDD RED/GREEN) + 3 integration

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD IntelFeedRouter, subscription filtering, log rotation | 03fe6b0 | intel_feed.py, event_logger.py, tests/test_feeds.py |
| 2 | Wire IntelFeedRouter and subscriptions into api_main.py | 9810e86 | api_main.py, tests/test_feeds.py |

## Test Results

- `test_feeds.py`: 12/12 passed
- Full suite: 412/412 passed, 0 failures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing coverage] Extended intel_router.emit to additional log_event call sites**
- **Found during:** Task 2
- **Issue:** Plan specified 7 log_event calls to replace, but api_main had additional log_event("command") calls for `set_autonomy_level`, `set_drone_autonomy`, `approve_transition`, `reject_transition`, `request_swarm`, `release_swarm` that also needed migration to keep "no remaining log_event(command)" acceptance criterion clean
- **Fix:** Replaced all 15 command-type log_event calls with intel_router.emit
- **Files modified:** src/python/api_main.py

## Self-Check: PASSED

- FOUND: src/python/intel_feed.py
- FOUND: src/python/tests/test_feeds.py
- FOUND: commit 03fe6b0
- FOUND: commit 9810e86
