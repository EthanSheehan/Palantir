# Pre-commit Hooks (W1-016)

## Summary
Add `.pre-commit-config.yaml` with ruff, black, mypy, and eslint hooks to catch formatting and type issues before commit.

## Files to Modify
- None (new files only)

## Files to Create
- `.pre-commit-config.yaml` — Pre-commit hook configuration
- `Makefile` — (partial, `make lint` target — shared with W1-018)

## Test Plan (TDD — write these FIRST)
1. `test_pre_commit_config_valid_yaml` — Config file is valid YAML
2. `test_all_hooks_pass_on_current_codebase` — `pre-commit run --all-files` passes (or document known failures to fix)

## Implementation Steps
1. Create `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.x.y
       hooks:
         - id: ruff
           args: [--fix]
         - id: ruff-format
     - repo: https://github.com/pre-commit/mirrors-mypy
       rev: v1.x.y
       hooks:
         - id: mypy
           additional_dependencies: [pydantic, fastapi]
     - repo: https://github.com/pre-commit/mirrors-eslint
       rev: v9.x.y
       hooks:
         - id: eslint
           files: src/frontend-react/.*\.(ts|tsx)$
   ```
2. Add `make lint` target: `pre-commit run --all-files`
3. Run `pre-commit install` to activate
4. Run `pre-commit run --all-files` and fix any failures

## Verification
- [ ] `pre-commit run --all-files` passes
- [ ] `make lint` works
- [ ] Hooks fire on `git commit`

## Rollback
- Delete `.pre-commit-config.yaml`; run `pre-commit uninstall`
