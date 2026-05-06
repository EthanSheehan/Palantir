---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# W1-C: TheaterSelector FIX-17 + FIX-18

## Status: PASS

## Changes Made

File: `src/frontend-react/src/panels/mission/TheaterSelector.tsx`

### FIX-17 — Error swallowed, no dropdown revert
- Captured `previous` selected value before optimistic update
- Replaced `.catch(console.error)` with `.catch((err) => { console.error(err); setSelected(previous); })`
- On failure: dropdown reverts to the previous theater

### FIX-18 — No loading state, dropdown spammable
- Added `const [loading, setLoading] = useState(false)`
- Set `loading=true` before `switchTheater()` call
- Set `loading=false` in `.finally()` block
- Added `disabled={loading}` to `<HTMLSelect>` — prevents interaction during the REST call

## No regressions
- Unrelated code (fetchTheaters, formatName, JSX structure) left untouched
- No new imports added
