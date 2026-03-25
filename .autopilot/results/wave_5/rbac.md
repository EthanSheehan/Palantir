# W5-006: Multi-User RBAC + JWT Auth

**Status: PASS**
**Tests: 39 new tests (all passing). 87 total across rbac + auth + hitl suites.**

## Files Created / Modified

- `src/python/rbac.py` — new module: Role enum, UserSession, create_token, validate_token, check_permission, PERMISSION_MATRIX
- `src/python/hitl_manager.py` — added `operator_id` param to approve/reject/retask_nomination and _make_decision/_transition_entry
- `src/python/tests/test_rbac.py` — 39 TDD tests (written before implementation)

## Implementation Summary

### Role enum
OBSERVER < OPERATOR < COMMANDER < ADMIN (numeric level comparison)

### Permission matrix
- OBSERVER: subscribe, subscribe_sensor_feed, sitrep queries
- OPERATOR: drone ops (move, follow, paint, intercept, swarm, coverage mode)
- COMMANDER: HITL gates (approve/reject nomination, authorize/reject COA, set_autonomy_level)
- ADMIN: config_update, admin_reset, set_roe, reset, SET_SCENARIO

### AUTH_DISABLED
Defaults to `true` (env var) for backward compat. When true:
- validate_token() returns dev ADMIN UserSession regardless of input
- check_permission() always returns True

### JWT
- PyJWT HS256, signed with JWT_SECRET env var
- Payload: sub (user_id), role, iat, exp
- Default expiry: 24h

### HITL operator identity
approve_nomination / reject_nomination / retask_nomination now accept optional `operator_id` kwarg.
It is recorded in the decision dict and audit log. Backward compatible (defaults to None).

## Dependency
PyJWT installed system-wide (python3 -m pip install PyJWT). Not yet in requirements.txt — add if needed.
