---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# FIX-14: StrikeBoardCoa REJECT Button Label

## Status: PASS

## Fix Applied

**File:** `src/frontend-react/src/panels/mission/StrikeBoardCoa.tsx`

**Change:** Renamed REJECT button label from `"REJECT"` to `"Reject Entry"` (line 46).

## Analysis

- The REJECT button sends `{ action: 'reject_coa', entry_id }` — no `coa_id` included.
- The AUTHORIZE button correctly sends `{ action: 'authorize_coa', entry_id, coa_id, rationale }` — per-COA scope.
- The mismatch means REJECT operates at entry level while AUTHORIZE operates at COA level.
- Renaming to "Reject Entry" accurately describes the actual behavior without requiring backend changes.

## AUTHORIZE Button Review

AUTHORIZE correctly passes `coa_id` — its label "AUTHORIZE" (now consistent with per-COA scope) is accurate. No change needed.

## Scope

Minimal label-only fix. Per-COA rejection would require adding `coa_id` to the backend `reject_coa` handler, which is out of scope for this ticket.
