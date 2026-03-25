# UX Quick Fixes — Dead Buttons, Shortcuts (W1-023)

## Summary
Fix dead buttons (Range, Detail with empty onClick), add keyboard shortcuts for critical operations (Escape=MANUAL, A/R=approve/reject, ?=help overlay).

## Files to Modify
- `src/frontend-react/src/components/` — Fix dead buttons: either hide them, wire up real functionality, or show "Coming soon" tooltip
- `src/frontend-react/src/App.tsx` — Add global keyboard event listener for shortcuts

## Files to Create
- `src/frontend-react/src/components/KeyboardShortcutHelp.tsx` — Help overlay component (? key)

## Test Plan (TDD — write these FIRST)
1. `test_escape_sets_manual_mode` — Pressing Escape sends `set_autonomy_level` MANUAL action
2. `test_a_key_approves_nomination` — Pressing A approves the focused/first pending nomination
3. `test_r_key_rejects_nomination` — Pressing R rejects the focused/first pending nomination
4. `test_question_mark_shows_help` — Pressing ? toggles shortcut help overlay
5. `test_dead_buttons_not_empty_onclick` — No buttons with `onClick={() => {}}` remain

## Implementation Steps
1. Find dead buttons: `grep -r "onClick={() => {}}" src/frontend-react/src/`
   - For Range button: hide or add tooltip `title="Coming in Wave 2"`
   - For Detail button: hide or add tooltip
2. Add global keyboard listener in `App.tsx` or a `useKeyboardShortcuts` hook:
   ```tsx
   useEffect(() => {
     const handler = (e: KeyboardEvent) => {
       if (e.key === 'Escape') sendWsAction('set_autonomy_level', { level: 'MANUAL' });
       if (e.key === 'a' && !isInputFocused()) sendWsAction('approve_nomination', { id: firstPendingId });
       if (e.key === 'r' && !isInputFocused()) sendWsAction('reject_nomination', { id: firstPendingId });
       if (e.key === '?') setShowShortcutHelp(prev => !prev);
     };
     window.addEventListener('keydown', handler);
     return () => window.removeEventListener('keydown', handler);
   }, []);
   ```
3. Create `KeyboardShortcutHelp.tsx`: simple overlay listing all shortcuts
4. Ensure shortcuts don't fire when typing in text inputs

## Verification
- [ ] No empty `onClick` handlers remain
- [ ] Escape forces MANUAL mode
- [ ] A/R keys work on pending nominations
- [ ] ? shows help overlay
- [ ] Shortcuts don't fire during text input

## Rollback
- Remove keyboard listener; revert button changes; delete KeyboardShortcutHelp.tsx
