# W1-015: pyproject.toml + Makefile Results

## Status: PASS

## Files Created
- `pyproject.toml` — Project metadata, pinned deps, ruff/mypy/pytest/coverage config
- `Makefile` — Standard dev targets: setup, run, demo, test, test-cov, lint, typecheck, dev-install, build, clean

## pyproject.toml Verification
- **TOML parse**: `tomli.load(open('pyproject.toml','rb'))` → OK
- Note: venv is Python 3.9 (broken interpreter path from directory move); used `tomli` backport instead of `tomllib` for verification

## Dependency Versions Pinned (from venv dist-info)
| Package | Pinned Version |
|---------|---------------|
| fastapi | 0.128.8 |
| uvicorn | 0.39.0 |
| pydantic | 2.12.5 |
| pydantic-settings | 2.11.0 |
| python-dotenv | 1.2.1 |
| structlog | 25.5.0 |
| websockets | 15.0.1 |
| requests | 2.32.5 |
| numpy | 2.0.2 |
| scipy | 1.13.1 |
| opencv-python | 4.13.0.92 |
| anthropic | 0.85.0 |
| google-genai | 1.47.0 |
| ollama | 0.6.1 |
| PyYAML | 6.0.3 |

Note: langchain/langgraph not installed in venv — kept with `>=` lower bounds from requirements.txt.

## Test Results
- **Before**: 3 collection errors (hypothesis, scipy not installed)
- **After installing hypothesis + scipy**: `537 passed, 3 failed` in 149s
- 3 pre-existing failures (unrelated to this task):
  - `test_jamming_enemy_detected_by_sigint`
  - `test_pattern_analyzer_handles_no_targets`
  - `test_rtb_eventually_reaches_home_and_goes_idle`

## Tool Config
- `[tool.ruff]`: line-length=120, target-version="py311", select E/F/W/I
- `[tool.pytest.ini_options]`: testpaths=src/python/tests, addopts=-q, asyncio_mode=auto
- `[tool.mypy]`: python_version="3.11", ignore_missing_imports=true
- `[tool.coverage.report]`: fail_under=80
