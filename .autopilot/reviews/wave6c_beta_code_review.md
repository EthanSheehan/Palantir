# Wave 6C-Beta Code Review

**Reviewer:** code-reviewer agent
**Date:** 2026-03-26
**Files Reviewed:**
- `src/frontend-react/src/overlays/GlobalAlertCenter.tsx`
- `src/frontend-react/src/overlays/FloatingStrikeBoard.tsx`
- `src/frontend-react/src/App.tsx` (recent additions)
- `docs/asyncapi.yaml`
- `docs/websocket_protocol.md`

---

## Findings

### MEDIUM — GlobalAlertCenter: transition alert fires on every render when transitions are non-empty

**File:** `GlobalAlertCenter.tsx:113-127`

The `pendingTransitions` effect has no deduplication guard. Every time `pendingTransitions` changes (any key added/removed/modified), it reads the last entry and fires an alert unconditionally if `count > 0`. This means:
- If a new key is added it fires correctly.
- If an *existing* key's value is updated (e.g. `expires_at` tick), it fires a duplicate alert.
- It never stops firing as long as there is at least one pending transition — there is no ref tracking the previously seen drone IDs.

**Fix:** Track seen drone IDs in a `useRef<Set<string>>` and only alert for new keys, clearing the entry when the key is removed.

---

### MEDIUM — GlobalAlertCenter: nomination alert uses wrong index for "newest" entry

**File:** `GlobalAlertCenter.tsx:82`

```ts
const newest = pending[pending.length - 1];
```

`strikeBoard` is filtered down to `PENDING` entries, then the last one is treated as "newest". However, the strike board array is appended at the tail by the backend, so this is likely to pick up an existing (already-alerted) nomination rather than the new one. The guard only checks that `pending.length > prevPendingCount.current`, but doesn't identify *which* entry is actually new.

**Fix:** Diff the pending IDs against a `useRef<Set<string>>` of already-seen IDs, and alert only for entries whose `id` has not been seen before.

---

### MEDIUM — GlobalAlertCenter: `addAlert` is recreated every render, causing stale closure risk

**File:** `GlobalAlertCenter.tsx:59-62`

`addAlert` is a plain function defined inside the component body. All four `useEffect` hooks close over it. Because `addAlert` is redefined every render, the effects do not stale-close over an old version (they re-run only when their deps change, by which point `addAlert` is fresh), but this pattern means ESLint's exhaustive-deps rule will complain about the missing `addAlert` dep in each effect. Wrapping `addAlert` in `useCallback` with a `[]` dep (since `setAlerts` from `useState` is stable) eliminates both the lint noise and any future stale-closure risk if deps ever change.

---

### MEDIUM — GlobalAlertCenter: auto-dismiss interval recreated on every alert change

**File:** `GlobalAlertCenter.tsx:130-137`

The interval is keyed on `alerts.length`. Adding or removing a single alert tears down and re-creates the interval, briefly skipping a 1-second tick. This is cosmetically minor but means alerts near their 10-second boundary can be extended by up to 1 second each time a new alert arrives. The interval should have an empty dep array `[]` and run unconditionally, or be a single long-lived interval for the component lifetime.

---

### MEDIUM — FloatingStrikeBoard: countdown uses mount-time baseline, not entry creation time

**File:** `FloatingStrikeBoard.tsx:30`

```ts
const expiresAt = useRef(Date.now() / 1000 + 300).current;
```

`NominationRow` mounts when the entry first becomes PENDING. The 300-second window is anchored to component mount, not to the nomination's actual creation time. If the backend already tracked the nomination for 60 seconds before the frontend mounted (e.g. after reconnect), the displayed countdown is 60 seconds too generous.

`StrikeEntry` does not currently carry a `created_at` or `expires_at` field. Until the backend exposes one, this is acceptable, but should be noted as a known limitation with a `// TODO` comment rather than silently being inaccurate.

---

### LOW — FloatingStrikeBoard: `useSendMessage` called inside a non-exported component that renders in a list

**File:** `FloatingStrikeBoard.tsx:28`

`NominationRow` calls `useSendMessage()` per row. Each row re-subscribes to `WebSocketContext`. This is correct and safe — `useSendMessage` just returns the stable `sendMessage` ref from context, so there is no unnecessary re-render. No code change required, but consider hoisting `sendMessage` into `FloatingStrikeBoard` and passing it as a prop if the component tree grows, to avoid coupling list-item components to context.

---

### LOW — GlobalAlertCenter: `unread` count label reads as absolute count, not "unread since open"

**File:** `GlobalAlertCenter.tsx:139,167`

`const unread = alerts.length` — the badge shows total alerts in state, not alerts since the panel was last opened. Once alerts auto-dismiss the count goes down, which is fine. But if the user opens and closes the panel, all visible alerts still count as "unread". The semantic mismatch is minor for a tactical UI but worth noting. A `lastOpenedAt` ref clearing a "seen" set on open would make it semantically correct.

---

### LOW — asyncapi.yaml: duplicate YAML key in `SetActionAutonomy` example

**File:** `docs/asyncapi.yaml:379-380`

```yaml
payload:
  action: set_action_autonomy
  action: ENGAGE        # ← duplicate key
```

YAML parsers treat duplicate keys as undefined behavior (most take the last value). The example payload loses the `action: set_action_autonomy` field. The correct field name for the action type enum is likely `action_type` or the second key should be renamed. Cross-reference the `SetActionAutonomyPayload` schema to confirm, then use the correct key name.

**Severity:** LOW for docs (no runtime impact), but misleading for API consumers.

---

### LOW — App.tsx: keyboard shortcut 'B' for Strike Board conflicts with potential Blueprint focus traps

**File:** `App.tsx:83-86`

The guard `if (tag === 'input' || tag === 'textarea') return` correctly avoids firing inside form fields, but Blueprint `Dialog`, `Popover`, and `OverlayToaster` can capture keyboard events before they bubble to `window`. If a Blueprint overlay is open, pressing B may silently fail. This matches the existing pattern for G/L/N shortcuts so it is consistent — but all shortcuts share this limitation.

No code change required; document in the keyboard-shortcut help text or tooltip.

---

### LOW — GlobalAlertCenter: `Button` (Blueprint) mixed with native `<button>` in the same panel

**File:** `GlobalAlertCenter.tsx:204-219, 288-300`

The "Clear all" and dismiss (×) controls use raw `<button>` elements while the action CTA uses Blueprint `<Button>`. This produces inconsistent focus ring and keyboard accessibility behavior. Either use Blueprint `<Button minimal>` throughout or use plain `<button>` with consistent styling, but don't mix the two in the same panel.

---

### LOW — websocket_protocol.md: `generate_sitrep` listed as alias but not in asyncapi.yaml

**File:** `docs/websocket_protocol.md:214`

The quick-reference table lists `generate_sitrep` as an alias for `sitrep_query`, but `asyncapi.yaml` only defines `SitrepQuery`. If the backend truly handles both, add a note in the asyncapi spec. If `generate_sitrep` is not implemented, remove it from the protocol doc to avoid confusion.

---

## Summary

| Severity | Count |
|----------|-------|
| HIGH     | 0     |
| MEDIUM   | 4     |
| LOW      | 6     |

**Priority fixes:** The transition alert storm (MEDIUM #1) and nomination deduplication bug (MEDIUM #2) could produce noisy/incorrect alerts in production. Fix both before release. The asyncapi duplicate key (LOW) should be corrected as it makes the spec invalid for tooling.
