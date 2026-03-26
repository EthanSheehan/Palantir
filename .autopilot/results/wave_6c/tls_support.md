# TLS Support — Wave 6C Result

## Status: COMPLETE

## Changes

### `src/python/config.py`
- Added `ssl_enabled: bool = False` — explicit TLS enable flag
- Added `ssl_certfile: str | None = None` — path to PEM certificate
- Added `ssl_keyfile: str | None = None` — path to PEM private key
- Added `allowed_origins: list[str]` — WebSocket origin allowlist (defaults: `http://localhost:3000`, `http://localhost:8000`)
- Added `@model_validator(mode="after")` — validates that both certfile and keyfile are provided when `ssl_enabled=True`

### `src/python/api_main.py`
- Added `_LOCALHOST_HOSTS` constant (`localhost`, `127.0.0.1`, `::1`)
- Added `_is_origin_allowed(origin)` — origin checking helper:
  - `None` origin → allowed (non-browser clients)
  - Localhost hosts → always allowed (dev bypass)
  - IPv6 bracket notation (`[::1]`) handled correctly
  - Non-localhost → must appear in `settings.allowed_origins`
- WebSocket endpoint now checks origin before accepting; rejects with code 4003 if disallowed
- `uvicorn.run()` passes `ssl_certfile`/`ssl_keyfile` when `ssl_enabled=True`

### `src/python/tests/test_tls_config.py` (new)
- 18 tests covering:
  - SSL defaults (disabled, no cert/key)
  - SSL enabled with both files succeeds
  - `ssl_enabled=True` with missing certfile raises `ValidationError`
  - `ssl_enabled=True` with missing keyfile raises `ValidationError`
  - `ssl_enabled=True` with neither raises `ValidationError`
  - `ssl_enabled=False` requires no files
  - `allowed_origins` defaults include both localhost ports
  - `allowed_origins` is configurable via env var
  - Origin checking: localhost always allowed (IPv4, IPv6 bracket, any port)
  - Origin checking: `None` origin allowed
  - Origin checking: listed origin passes
  - Origin checking: unlisted origin rejected
  - `wss://` scheme localhost allowed
  - HTTPS non-localhost in list passes
  - HTTPS non-localhost not in list rejected
  - Origin with path component handled
  - Empty allowlist blocks non-localhost
  - Localhost bypass regardless of allowlist

## Test Results
```
18 passed in 0.29s
```
