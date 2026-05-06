---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# FIX-12: Remove SUPPORT Button from DroneModeButtons.tsx

**Status:** PASS

## Change Summary

Removed the SUPPORT mode button from `src/frontend-react/src/panels/assets/DroneModeButtons.tsx`.

### Removed from `MODES` array (line 19 original):
```ts
{ label: 'SUPPORT', action: 'support_target', color: MODE_STYLES.SUPPORT.color, needsTarget: true },
```

### Removed from `ACTION_FOR_MODE` map (line 28 original):
```ts
SUPPORT: 'support_target',
```

## Verification

- No dead code, orphaned imports, or broken formatting left behind
- `MODE_STYLES` import retained — still used for `MODE_STYLES.VERIFY.color`
- Remaining 5 buttons: SEARCH, FOLLOW, PAINT, INTERCEPT, VERIFY — all intact with correct actions, colors, and `needsTarget` flags
- `flex: 1` layout on each button self-adjusts to 5 buttons from 6 — no layout breakage
- No backend handler needed; the broken `support_target` action path is fully eliminated from the UI
