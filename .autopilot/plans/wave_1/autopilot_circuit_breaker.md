# Demo Autopilot Circuit Breaker (W1-014)

## Summary
Add safety limits to demo autopilot: max auto-approvals per minute, halt if no DASHBOARD client connected, per-session engagement cap. Log circuit breaker activations to Intel Feed.

## Files to Modify
- `src/python/api_main.py` — Add circuit breaker logic to `demo_autopilot()` function

## Files to Create
- `src/python/tests/test_autopilot_circuit_breaker.py` — Circuit breaker tests

## Test Plan (TDD — write these FIRST)
1. `test_max_approvals_per_minute` — After N approvals in 60s, further approvals blocked
2. `test_halt_no_dashboard_connected` — Autopilot pauses when no DASHBOARD clients are connected for 30s
3. `test_session_engagement_cap` — Total engagements per session limited
4. `test_circuit_breaker_logged_to_intel_feed` — Breaker activation produces SAFETY event in Intel Feed
5. `test_circuit_breaker_resets_after_cooldown` — After cooldown period, approvals resume

## Implementation Steps
1. Add configuration constants (or to `config.py`):
   ```python
   MAX_AUTO_APPROVALS_PER_MINUTE = 10
   NO_DASHBOARD_TIMEOUT_S = 30
   MAX_SESSION_ENGAGEMENTS = 50
   ```
2. In `demo_autopilot()`, track:
   - `approval_timestamps: deque` — sliding window of approval times
   - `session_engagement_count: int` — total engagements this session
   - `last_dashboard_seen: float` — timestamp of last DASHBOARD heartbeat
3. Before each auto-approval, check all three limits
4. On breaker activation, publish SAFETY event to Intel Feed and log warning

## Verification
- [ ] Autopilot stops approving after rate limit hit
- [ ] Autopilot halts when all dashboard clients disconnect
- [ ] Intel Feed shows SAFETY events on breaker activation
- [ ] All existing tests pass

## Rollback
- Remove circuit breaker checks from `demo_autopilot()`
