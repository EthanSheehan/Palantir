# Wave 4A: Timeline Scrub + Historical Playback

**Status:** COMPLETE
**Date:** 2026-03-27

## Files Created

- `src/python/history_store.py` — SQLite snapshot persistence (every 5s, lightweight UAV+target positions only)
- `src/frontend-react/src/overlays/BottomTimelineDock.tsx` — Collapsible bottom timeline dock with scrub/playback

## Files Modified

- `src/python/api_main.py` — Added `HistoryStore` instantiation + two REST endpoints (`/api/history/range`, `/api/history/state`)
- `src/python/simulation_loop.py` — Added `history_store` parameter, calls `maybe_capture(state)` each tick
- `src/frontend-react/src/App.tsx` — Added `BottomTimelineDock` import, `timelineVisible` state, `T` keyboard shortcut, JSX render

## API Endpoints

- `GET /api/history/range` → `{start, end, count}` — available snapshot time range
- `GET /api/history/state?at=<timestamp>` → `{timestamp, state}` — closest snapshot at or before `at`

## Frontend

- Toggle with `T` key
- Collapsible header shows LIVE/HISTORICAL tag + "RETURN TO LIVE" button
- Expanded shows slider (Blueprint Slider) + play/pause button
- Scrubbing fires `grid_sentinel:historicalState` custom event with historical state data
- Snapshot count shown in header

## Tests

- `test_sim_integration.py::TestSetEnvironment::test_bad_weather_reduces_detection_rate` — pre-existing failure unrelated to this work
- All other tests pass
- Manual smoke test of HistoryStore confirms correct insert/query behavior
