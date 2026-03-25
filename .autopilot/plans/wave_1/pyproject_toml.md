# pyproject.toml with Pinned Dependencies (W1-015)

## Summary
Create `pyproject.toml` consolidating Python project config: pinned dependency versions, ruff/mypy/pytest configuration, and 80% coverage threshold.

## Files to Modify
- `requirements.txt` — Keep as-is for pip compatibility but pin versions to match pyproject.toml

## Files to Create
- `pyproject.toml` — Project metadata, pinned dependencies, tool config (ruff, mypy, pytest, coverage)

## Test Plan (TDD — write these FIRST)
1. `test_pyproject_toml_valid` — `tomllib` can parse the file without error
2. `test_all_requirements_have_upper_bounds` — Every dependency has a version pin or upper bound

## Implementation Steps
1. Read current `requirements.txt` to get all dependencies and their current versions
2. Create `pyproject.toml` with:
   - `[project]` section: name, version, description, python-requires
   - `[project.dependencies]`: all runtime deps with pinned versions (e.g., `fastapi==0.x.y`)
   - `[project.optional-dependencies]`: dev deps (pytest, hypothesis, ruff, mypy, black, pip-audit)
   - `[tool.ruff]`: line-length=120, select rules
   - `[tool.mypy]`: python_version, ignore_missing_imports
   - `[tool.pytest.ini_options]`: testpaths, addopts with coverage
   - `[tool.coverage.run]`: source paths
   - `[tool.coverage.report]`: fail_under=80
3. Pin all dependency versions to current installed versions
4. Verify `pip install -e .` works with the new pyproject.toml

## Verification
- [ ] `pip install -e ".[dev]"` succeeds
- [ ] `ruff check src/python/` runs
- [ ] `pytest --cov` enforces 80% threshold
- [ ] All existing tests pass

## Rollback
- Delete `pyproject.toml`; `requirements.txt` remains functional
