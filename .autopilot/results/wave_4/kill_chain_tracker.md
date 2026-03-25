# W4-007: F2T2EA Kill Chain Progress Indicator

## Status: COMPLETE

## Files Created
- `src/python/kill_chain_tracker.py` — KillChainPhase enum, KillChainStatus frozen dataclass, KillChainTracker class with `compute()` and `to_dict()`

## Files Modified
- `src/python/simulation_loop.py` — Added kill chain computation each tick, broadcasts `kill_chain` field in WebSocket payload
- `src/python/api_main.py` — Added `GET /api/kill-chain` REST endpoint

## Tests
- `src/python/tests/test_kill_chain_tracker.py` — 26 tests covering all phases, edge cases, serialization

## Design

### Phase Classification Logic
| Phase | Condition |
|-------|-----------|
| FIND | Target in DETECTED state |
| FIX | Target in CLASSIFIED state (no active drone tracking) |
| TRACK | Target actively tracked by drone in FOLLOW/PAINT/INTERCEPT mode |
| TARGET | Target in VERIFIED/NOMINATED/LOCKED state |
| ENGAGE | Target in ENGAGED state or strike board APPROVED/IN_FLIGHT |
| ASSESS | Target DESTROYED/ESCAPED or strike board HIT/MISS |

### Priority: ASSESS > ENGAGE > TARGET > TRACK > FIX > FIND
Each target appears in exactly one phase. Higher-priority phases take precedence.

### WebSocket Payload
```json
{
  "kill_chain": {
    "phases": [
      {"phase": "FIND", "target_count": 3, "target_ids": [1, 2, 3]},
      ...
    ],
    "total_tracked": 12
  }
}
```

### REST Endpoint
`GET /api/kill-chain` returns the same structure, computed fresh if no cached data.

## Test Results
- 1047 passed (full suite), 26 new kill chain tests
