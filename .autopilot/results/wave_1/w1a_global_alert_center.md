---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# FIX-11: GlobalAlertCenter deduplication field fix

## Status: PASS

## Problem
Line 83 used `entry.entry_id ?? entry.target_id` for nomination deduplication.
`StrikeEntry` type (types.ts:86-93) has neither `entry_id` nor `target_id` — only `id`.
Both fields evaluated to `undefined`, causing every nomination to always generate a new
alert (alert spam).

## Fix Applied
**File:** `src/frontend-react/src/overlays/GlobalAlertCenter.tsx`, line 83

```diff
- const entryId = entry.entry_id ?? entry.target_id;
+ const entryId = entry.id;
```

## Verification
- `StrikeEntry` in `src/frontend-react/src/store/types.ts` confirms `id: string` is the
  correct field (line 87).
- `CommandEvent` (types.ts:143-152) does have optional `entry_id` and `target_id` fields,
  but that is a different type used in the command events effect (line 105), not the
  strike board entries. That usage is correct and unchanged.
- The `seenNominationIds` Set now correctly tracks by `entry.id`, preventing duplicate
  alerts for the same strike board entry.
