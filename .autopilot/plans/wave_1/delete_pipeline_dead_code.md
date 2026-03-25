# Delete or Gut pipeline.py Dead Code (W1-005)

## Summary
Remove dead `pipeline.py` (blocking `input()` call, never used in WebSocket flow) and clean up `test_data_synthesizer.py` which references non-existent endpoints.

## Files to Modify
- `src/python/pipeline.py` — Delete entirely or gut to a stub with docstring pointing to `api_main.py`
- `src/python/test_data_synthesizer.py` — Delete or clean up (references non-existent `/ingest` endpoint)

## Files to Create
- None

## Test Plan (TDD — write these FIRST)
1. `test_no_blocking_input_in_codebase` — Grep verification: no `input()` calls in production code
2. `test_pipeline_import_still_works` — If kept as stub, verify import doesn't crash

## Implementation Steps
1. Delete `src/python/pipeline.py` entirely
2. Delete `src/python/test_data_synthesizer.py` (references non-existent `/ingest`)
3. Search for any imports of `pipeline` in the codebase and remove them
4. Verify no other module depends on these files

## Verification
- [ ] `grep -r "from.*pipeline import\|import pipeline" src/python/` returns zero hits (excluding tests)
- [ ] `grep -r "test_data_synthesizer" src/python/` returns zero hits
- [ ] All existing tests pass
- [ ] `./palantir.sh --demo` runs without import errors

## Rollback
- Restore `pipeline.py` and `test_data_synthesizer.py` from git
