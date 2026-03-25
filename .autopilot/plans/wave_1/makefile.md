# Makefile with Standard Targets (W1-018)

## Summary
Create a Makefile with standard development targets: setup, run, demo, test, lint, build.

## Files to Modify
- None

## Files to Create
- `Makefile` — Standard development targets

## Test Plan (TDD — write these FIRST)
1. `test_makefile_exists` — File exists and is valid Make syntax
2. `test_make_test_runs_pytest` — `make test` executes pytest successfully

## Implementation Steps
1. Create `Makefile`:
   ```makefile
   .PHONY: setup run demo test lint build clean

   VENV := ./venv/bin
   PYTHON := $(VENV)/python3
   PIP := $(VENV)/pip

   setup:
   	$(PIP) install -r requirements.txt
   	cd src/frontend-react && npm install

   run:
   	./palantir.sh

   demo:
   	./palantir.sh --demo

   test:
   	$(PYTHON) -m pytest src/python/tests/ -v --tb=short

   test-cov:
   	$(PYTHON) -m pytest src/python/tests/ --cov=src/python --cov-report=term-missing --cov-fail-under=80

   lint:
   	$(PYTHON) -m ruff check src/python/
   	cd src/frontend-react && npx eslint src/

   build:
   	cd src/frontend-react && npm run build

   clean:
   	find . -type d -name __pycache__ -exec rm -rf {} +
   	find . -type f -name "*.pyc" -delete
   ```

## Verification
- [ ] `make test` runs all tests
- [ ] `make lint` checks Python and JS
- [ ] `make demo` launches demo mode
- [ ] `make setup` installs all dependencies

## Rollback
- Delete `Makefile`
