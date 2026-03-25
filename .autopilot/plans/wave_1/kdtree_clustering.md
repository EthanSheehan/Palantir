# KD-Tree Clustering with scipy.spatial (W1-021)

## Summary
Replace O(n^2) distance loop in battlespace_assessment.py threat clustering with scipy.spatial.KDTree for O(n log n) performance.

## Files to Modify
- `requirements.txt` — Add `scipy` (if not already present)
- `src/python/battlespace_assessment.py` — Replace distance loop in `identify_threat_clusters()` with KDTree

## Files to Create
- `src/python/tests/test_kdtree_clustering.py` — Tests for KDTree-based clustering

## Test Plan (TDD — write these FIRST)
1. `test_kdtree_same_clusters_as_original` — KDTree produces identical clusters to current O(n^2) implementation
2. `test_kdtree_empty_targets` — Empty input returns empty clusters
3. `test_kdtree_single_target` — Single target forms one cluster
4. `test_kdtree_distant_targets_separate_clusters` — Targets beyond threshold form separate clusters
5. `test_all_assessment_tests_pass` — All 21 existing assessment tests still pass

## Implementation Steps
1. Ensure `scipy` in `requirements.txt`
2. In `battlespace_assessment.py`, find `identify_threat_clusters()`:
   - Extract target positions into numpy array
   - Build `KDTree(positions)`
   - Use `tree.query_ball_point()` or `tree.query_pairs(threshold)` for neighbor finding
   - Build clusters from neighbor pairs (union-find or iterative merge)
3. Keep the same return type and cluster structure
4. Run existing tests to verify behavioral equivalence

## Verification
- [ ] All 21 battlespace assessment tests pass
- [ ] Clustering produces same results as original
- [ ] Performance improvement measurable at 100+ targets
- [ ] No scipy import errors

## Rollback
- Revert `identify_threat_clusters()` to original O(n^2) loop
