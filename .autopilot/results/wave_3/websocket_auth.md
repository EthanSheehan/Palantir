# W3-006: WebSocket Token Authentication — Results

## Status: COMPLETE

## Files Created
- `src/python/auth.py` — TokenTier enum, AuthConfig frozen dataclass, AuthManager class
- `src/python/tests/test_auth.py` — 31 tests covering all acceptance criteria

## Files Modified
- `src/python/config.py` — Added auth_enabled, demo_token, dashboard_tokens, simulator_tokens, admin_tokens fields
- `src/python/api_main.py` — Auth integration: token check on IDENTIFY, tier storage per connection, authorization check before action dispatch

## Architecture

### Token Tiers
- **SIMULATOR**: DRONE_FEED, TRACK_UPDATE, TRACK_UPDATE_BATCH only
- **DASHBOARD**: All actions except admin-only (set_roe, config_update, admin_reset)
- **ADMIN**: All actions

### Auth Flow
1. Client sends IDENTIFY with optional `token` field
2. If `auth_enabled=True` and token invalid → error + disconnect (code 4001)
3. Authenticated tier stored in `clients[ws]["tier"]`
4. Every subsequent action checked against tier permissions
5. Unauthorized actions get `{"error": "unauthorized", "action": ..., "required_tier": "DASHBOARD"}`

### Backward Compatibility
- `auth_enabled` defaults to `False` — existing tests and clients unaffected
- `DEMO_TOKEN=dev` provides local dev bypass (authenticates as DASHBOARD)
- Unauthenticated connections default to DASHBOARD tier when auth is disabled

## Test Results
- 31/31 auth tests passing
- Full test suite: no regressions (pre-existing failures in enemy_uavs, hungarian_swarm, mission_store are unrelated)

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| AUTH_ENABLED | false | Enable WebSocket token auth |
| DEMO_TOKEN | dev | Dev bypass token (DASHBOARD tier) |
| DASHBOARD_TOKENS | "" | Comma-separated DASHBOARD API keys |
| SIMULATOR_TOKENS | "" | Comma-separated SIMULATOR API keys |
| ADMIN_TOKENS | "" | Comma-separated ADMIN API keys |
