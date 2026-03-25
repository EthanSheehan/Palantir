# GitHub Actions CI Pipeline (W1-017)

## Summary
Create a GitHub Actions workflow that runs ruff linting, pytest with coverage, and frontend ESLint on every push and PR. Add a `/health` endpoint for smoke testing.

## Files to Modify
- `src/python/api_main.py` — Add `/health` and `/ready` GET endpoints

## Files to Create
- `.github/workflows/test.yml` — CI workflow definition
- `src/python/tests/test_health_endpoint.py` — Tests for health endpoint

## Test Plan (TDD — write these FIRST)
1. `test_health_endpoint_returns_200` — GET /health returns 200 with status JSON
2. `test_ready_endpoint_returns_200` — GET /ready returns 200 when sim is initialized
3. `test_health_includes_version` — Health response includes app version

## Implementation Steps
1. Add endpoints to `api_main.py`:
   ```python
   @app.get("/health")
   async def health():
       return {"status": "ok", "version": "2.0.0"}

   @app.get("/ready")
   async def ready():
       return {"status": "ready", "sim_initialized": sim is not None}
   ```
2. Create `.github/workflows/test.yml`:
   ```yaml
   name: CI
   on: [push, pull_request]
   jobs:
     backend:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: '3.12' }
         - run: pip install -r requirements.txt
         - run: pip install ruff pytest pytest-cov
         - run: ruff check src/python/
         - run: pytest src/python/tests/ --cov=src/python --cov-report=xml --cov-fail-under=80
     frontend:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with: { node-version: '20' }
         - run: cd src/frontend-react && npm ci && npx eslint src/
   ```

## Verification
- [ ] Workflow triggers on push and PR
- [ ] Backend job: ruff + pytest + coverage gate pass
- [ ] Frontend job: ESLint passes
- [ ] `/health` and `/ready` return 200

## Rollback
- Delete `.github/workflows/test.yml`; remove health endpoints
