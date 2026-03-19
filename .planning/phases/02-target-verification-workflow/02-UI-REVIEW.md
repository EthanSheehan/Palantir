# Phase 02 — UI Review

**Audited:** 2026-03-19
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md for phase 02)
**Screenshots:** Not captured (no dev server running at localhost:3000, 5173, or 8080)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Domain-specific, mission-appropriate labels throughout; one generic close button and one ambiguous empty state |
| 2. Visuals | 3/4 | Clear hierarchy on enemy cards with layered info zones; VERIFY button intent color conflicts with step dot color for current state |
| 3. Color | 2/4 | ~40 hardcoded hex values scattered across 10+ files; no token layer — color changes require multi-file hunts |
| 4. Typography | 2/4 | 8 distinct inline `fontSize` values (9–16px) with no Tailwind scale; mixed `rem` and `px` units in adjacent elements |
| 5. Spacing | 3/4 | Consistent 4/6/8/16px rhythm throughout; a few one-off values (gap: 12, marginBottom: 6, padding: 3) |
| 6. Experience Design | 3/4 | Loading, empty, and error states present for all primary lists; DroneCamPIP close button lacks aria-label; DroneModeButtons has no disabled visual when UAV is in RTB/IDLE mode |

**Overall: 16/24**

---

## Top 3 Priority Fixes

1. **40+ hardcoded hex values with no token layer** — color changes (e.g., rebranding accent, adjusting severity palette) require editing 10+ files with no single source of truth; replace with CSS custom properties or a `tokens.ts` file that `constants.ts` and inline styles both import from.

2. **8 distinct inline `fontSize` values without a scale** — mixed `px` / `rem` units (e.g., `0.6rem` in EnemyCard.tsx, `11` in FusionBar.tsx, `9` in VerificationStepper.tsx) make visual rhythm inconsistent and impossible to audit; establish a 4-step type scale (10/11/12/14px) and apply uniformly.

3. **DroneCamPIP close button is inaccessible** — the `×` button at `DroneCamPIP.tsx:41` has no `aria-label`, title, or tooltip; screen readers announce it as a literal multiplication sign; add `aria-label="Close drone camera"`.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**Strengths:**

- All primary CTAs are mission-specific: "VERIFY", "SEARCH", "FOLLOW", "PAINT", "INTERCEPT" — no generic "Submit" or "OK" patterns found (grep confirmed zero matches).
- Empty states are contextual: `EnemiesTab.tsx:48` renders "No hostile entities detected." and `AssetsTab.tsx:9` renders "No UAVs Active." — domain-appropriate phrasing.
- The tactical assistant empty state (`AssistantWidget.tsx:25`) uses "Waiting for intel..." which is appropriate for the context.
- Error handling is minimal but honest — `TheaterSelector.tsx:12` silently falls back to `['romania']` on fetch failure with no user-facing message.

**Issues:**

- `DroneCamPIP.tsx:51` — The close button renders the bare `×` character with no surrounding label context. While visually unambiguous in the PIP header, it has no programmatic label.
- `AssistantWidget.tsx:25` — "Waiting for intel..." is fine, but the StrikeBoard empty state (`StrikeBoard.tsx:21`) reads "No active strike packages." — inconsistent tone (period vs no period, active vs passive construction).
- `DroneModeButtons.tsx:77` — When a target-dependent mode button is clicked without a target, the button text momentarily changes to "Pick target" for 600ms. This is the only truly generic/imperative label and it is ephemeral, so minor, but "SELECT TARGET" would be more consistent with the all-caps tactical register used elsewhere.

---

### Pillar 2: Visuals (3/4)

**Strengths:**

- EnemyCard has a well-structured 3-zone layout: identity row (type badge + ID + sensor badge + concealed tag), state badge + tracker tags, then FusionBar, then VerificationStepper. Information density is appropriate for a C2 context.
- VerificationStepper (`VerificationStepper.tsx`) provides clear progressive disclosure — step dots encode past/present/future state with three distinct colors, and the progress bar gives analog confidence feedback below the discrete steps. This is the principal new deliverable and it reads clearly.
- The VERIFY button appears only on CLASSIFIED targets (`VerificationStepper.tsx:92`), satisfying the conditional-visibility requirement with zero ambiguity.
- Selection highlight is implemented at both the card level (border color in `EnemyCard.tsx:75`) and on the Cesium globe (white text + colored background from 02-03 SUMMARY), creating cross-layer visual continuity.

**Issues:**

- The amber VERIFY button (`Intent.WARNING`) uses the same amber hue (`#D9822B`) as the current-step dot on CLASSIFIED targets. Two distinct interaction affordances (informational state indicator vs. actionable button) share a color, weakening the signal. The button should use `Intent.PRIMARY` (blue) or a unique distinct color to distinguish action from state.
- The step label abbreviations are truncated via `.slice(0, 4)` — "DETE", "CLAS", "VERI", "NOMI" — which saves space but "CLAS" and "VERI" are non-standard abbreviations. "DETD", "CLSD", "VRFD", "NOMD" would be more common in military notation, or 3-char: "DET", "CLS", "VRF", "NOM".
- The FusionBar ECharts chart (`FusionBar.tsx:59`) is fixed at `width: 120px` with no viewport-relative sizing. On narrow sidebar widths the stacked bar may overflow or compress other elements.
- The DroneCamPIP close control is a bare `<button>` rendering `×` in color `#666` — very low contrast against the dark `rgba(0,0,0,0.85)` background, likely failing WCAG AA (4.5:1 for small text).

---

### Pillar 3: Color (2/4)

**Issue summary: 40+ hardcoded hex values, no token layer.**

Hardcoded hex values found across files:

| File | Count | Examples |
|------|-------|---------|
| `constants.ts` | ~30 | All STATE_COLORS, TARGET_MAP, MODE_STYLES, SEVERITY_STYLES values |
| `EnemyCard.tsx` | ~8 | `#ef4444`, `#ff6400`, `#a78bfa`, `#94a3b8`, `#475569`, `#64748b`, `#000` |
| `DemoBanner.tsx` | ~5 | `#ef4444`, `rgba(239,68,68,0.25)`, `#94a3b8`, `#64748b` |
| `DroneModeButtons.tsx` | ~4 | `#22c55e`, `#a78bfa`, `#ef4444`, `#ff6400` |
| `DroneCamPIP.tsx` | ~3 | `#00ff00`, `#666`, `rgba(0,0,0,0.85)` |
| `FusionBar.tsx` | ~3 | `#4A90E2`, `#7ED321`, `#F5A623` |
| `VerificationStepper.tsx` | ~3 | `#0F9960`, `#D9822B`, `#5C7080` |

**Specific problems:**

1. `DroneModeButtons.tsx:14-17` duplicates the exact same colors already defined in `constants.ts:MODE_STYLES` but as a local inline array — the same color for FOLLOW (`#a78bfa`) appears in two places. A change to the FOLLOW color requires two file edits.
2. `DemoBanner.tsx:42` hardcodes `rgba(239,68,68,0.25)` — this is the alpha variant of `#ef4444` (danger/ENGAGED). This pattern appears 4 times across files without an alpha-variant token.
3. `DroneCamPIP.tsx:38` uses `#00ff00` (pure green) for the "DRONE CAM" overlay label — this is visually coherent (military HUD aesthetic) but is not represented in `constants.ts`. It's effectively an orphan color.
4. `FusionBar.tsx:5-8` defines its own `SENSOR_COLORS` dict (`#4A90E2`, `#7ED321`, `#F5A623`) with no relationship to any color in `constants.ts`. These could collide or diverge from the STATE_COLORS palette.

**What works:** `constants.ts` centralizes most recurring UI colors (STATE_COLORS, TARGET_MAP, MODE_STYLES, SEVERITY_STYLES). The architecture is correct — the token layer exists — but it is incomplete. The solution is to extend `constants.ts` to cover sensor colors, alpha variants, and structural colors, then eliminate the duplications.

---

### Pillar 4: Typography (2/4)

**Font size distribution (inline `fontSize` values):**

| Value | Count | Usage |
|-------|-------|-------|
| 12 | 11 | Body text, assistant messages |
| 11 | 8 | Timestamps, tags, sensor badge |
| 9 | 2 | VerificationStepper step labels |
| 10 | 2 | DemoBanner labels |
| 13 | 2 | Message body in AssistantWidget |
| 14 | 1 | Various |
| 16 | 2 | Various |

Additionally, `EnemyCard.tsx` uses `rem`-based sizes: `0.6rem`, `0.65rem`, `0.7rem`, `0.8rem`, `0.85rem` — five distinct sizes in one component, none of which map to a declared scale.

**Problems:**

1. **8 distinct size values (9, 10, 11, 12, 13, 14, 16px) plus 5 distinct `rem` values in EnemyCard alone** — this is well over the 4-size guideline for a focused UI component.
2. **Mixed unit systems** — `fontSize: 11` (px) in `FusionBar.tsx:60` sits adjacent to `fontSize: '0.65rem'` in EnemyCard (approximately 10.4px at 16px base). These near-identical sizes will render slightly differently across browsers and zoom levels.
3. **No Tailwind text classes are used anywhere** — the project uses Blueprint + inline styles, so Tailwind's text scale is unavailable. This is by design, but without a corresponding token system the typography has drifted to 8+ values.
4. **`fontWeight` usage:** `600`, `700`, `800` all appear in EnemyCard.tsx alone. Three distinct weights in a single component — the `fontWeight: 800` on the "TGT" badge (`EnemyCard.tsx:100`) is likely unnecessary given `700` achieves sufficient emphasis.

**Recommended 4-step scale for this codebase (px-based, consistent with Blueprint):**

| Token | Value | Usage |
|-------|-------|-------|
| `--font-size-xs` | 9px | Step labels, micro-badges |
| `--font-size-sm` | 11px | Timestamps, secondary metadata |
| `--font-size-base` | 12px | Body, card content |
| `--font-size-md` | 14px | Section headers, panel titles |

---

### Pillar 5: Spacing (3/4)

**Dominant spacing values from inline styles:**

- `gap: 4`, `gap: 6`, `gap: 8` — consistent 2px-step micro-rhythm
- `padding: 8`, `padding: 16` — consistent 8px grid
- `marginBottom: 4`, `marginBottom: 8` — consistent

**Inconsistencies found:**

- `StrikeBoardEntry.tsx:27` uses `gap: 12` and `marginBottom: 6` — the 6 breaks the 4/8 rhythm; this is a minor deviation.
- `StrikeBoardCoa.tsx:27` uses `gap: 12, marginBottom: 6` — same pattern; likely copied from StrikeBoardEntry.
- `VerificationStepper.tsx:71` sets `marginBottom: 12` on the connector line `<div>` to optically align dots with the line — this is a visual adjustment, not a layout value, and is acceptable.
- `VerificationStepper.tsx:98` uses `marginTop: 4` on the VERIFY button — consistent with the 4-step rhythm.
- `DroneModeButtons.tsx:53` uses `gap: 4, marginBottom: 6` — the `6` is an outlier in the drone card context where `gap: 8` is used elsewhere.

Overall the 4/8/16 grid is well-maintained. The 6px outliers are in components added before this phase and are minor.

---

### Pillar 6: Experience Design (3/4)

**State coverage:**

| State type | Present | Components |
|-----------|---------|-----------|
| Empty state (no data) | Yes | EnemiesTab, AssetsTab, StrikeBoard, AssistantWidget |
| Loading state | Partial | No explicit spinner/skeleton for WebSocket reconnect |
| Error state | Partial | TheaterSelector catches fetch errors silently; no user-facing WebSocket error |
| Disabled state | Partial | DroneModeButtons pulses when no target selected, but no `disabled` attribute |
| Confirmation for destructive | N/A | No destructive actions in scope for this phase |

**Specific findings:**

1. **DroneCamPIP.tsx:41** — The close button is a bare `<button>` with no `aria-label`. Announced as "times" or "multiply" by screen readers. Fix: `aria-label="Close drone camera"`.

2. **DroneModeButtons.tsx:56-80** — FOLLOW, PAINT, and INTERCEPT buttons when no target is selected have no visual disabled state — they appear identical to the active SEARCH button. A user has no affordance that these buttons require a selection unless they click one and observe the 600ms pulse. Adding `opacity: 0.4` or a grayed border when `needsPickTarget` is true would communicate unavailability without the click-to-discover pattern.

3. **No WebSocket reconnect indicator** — the UI has no skeleton state or reconnect banner for when the WebSocket drops. The EnemiesTab would simply freeze with stale data. For a real-time C2 system this is a meaningful gap; a connection status indicator in the sidebar header would address it.

4. **TheaterSelector.tsx:12** — The `.catch(() => setTheaters(['romania']))` silently absorbs API failures. If the theater list fails to load, the selector silently shows only "romania" with no indication to the operator that the fetch failed. A fallback with a visible warning would prevent silent data loss.

5. **Hysteresis filter in EnemiesTab** is well-designed — once a target is seen, it stays visible while confidence > 0, preventing jitter. This is good UX for a high-frequency data feed.

6. **Cross-tab navigation from enemy card to UAV card** (clicking UAV tracker tag → jumps to ASSETS tab and selects drone) is a solid interaction that was added as a deviation from the original plan. It reduces navigation steps for operators.

---

## Registry Safety

No shadcn `components.json` found — registry audit skipped.

---

## Files Audited

**Phase 02 planning docs:**
- `.planning/phases/02-target-verification-workflow/02-01-PLAN.md`
- `.planning/phases/02-target-verification-workflow/02-01-SUMMARY.md`
- `.planning/phases/02-target-verification-workflow/02-02-PLAN.md`
- `.planning/phases/02-target-verification-workflow/02-02-SUMMARY.md`
- `.planning/phases/02-target-verification-workflow/02-03-PLAN.md`
- `.planning/phases/02-target-verification-workflow/02-03-SUMMARY.md`

**Frontend source (27 files):**
- `src/frontend-react/src/App.tsx`
- `src/frontend-react/src/shared/constants.ts`
- `src/frontend-react/src/panels/enemies/VerificationStepper.tsx`
- `src/frontend-react/src/panels/enemies/EnemyCard.tsx`
- `src/frontend-react/src/panels/enemies/EnemiesTab.tsx`
- `src/frontend-react/src/panels/enemies/FusionBar.tsx`
- `src/frontend-react/src/panels/enemies/SensorBadge.tsx`
- `src/frontend-react/src/panels/enemies/ThreatSummary.tsx`
- `src/frontend-react/src/panels/assets/AssetsTab.tsx`
- `src/frontend-react/src/panels/assets/DroneCard.tsx`
- `src/frontend-react/src/panels/assets/DroneModeButtons.tsx`
- `src/frontend-react/src/panels/assets/DroneCardDetails.tsx`
- `src/frontend-react/src/panels/assets/DroneActionButtons.tsx`
- `src/frontend-react/src/panels/mission/AssistantWidget.tsx`
- `src/frontend-react/src/panels/mission/MissionTab.tsx`
- `src/frontend-react/src/panels/mission/StrikeBoard.tsx`
- `src/frontend-react/src/panels/mission/StrikeBoardEntry.tsx`
- `src/frontend-react/src/panels/mission/StrikeBoardCoa.tsx`
- `src/frontend-react/src/panels/mission/GridControls.tsx`
- `src/frontend-react/src/panels/mission/TheaterSelector.tsx`
- `src/frontend-react/src/panels/Sidebar.tsx`
- `src/frontend-react/src/panels/SidebarTabs.tsx`
- `src/frontend-react/src/overlays/DroneCamPIP.tsx`
- `src/frontend-react/src/overlays/DemoBanner.tsx`
- `src/frontend-react/src/cesium/CameraControls.tsx`
- `src/frontend-react/src/cesium/CesiumContainer.tsx`
- `src/frontend-react/src/cesium/DetailMapDialog.tsx`
