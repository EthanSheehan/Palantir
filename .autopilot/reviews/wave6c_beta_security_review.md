# Wave 6C-Beta Security Review

**Scope:** `GlobalAlertCenter.tsx`, `FloatingStrikeBoard.tsx`, `App.tsx` (recent changes)
**Date:** 2026-03-26
**Reviewer:** security-reviewer agent

---

## Summary

Overall security posture is **GOOD**. The most important finding is the hardened `grid_sentinel:send` event bridge allowlist in `App.tsx`. No critical issues found. Two medium issues and three low issues require attention.

---

## Findings

### MEDIUM-1 — Unvalidated server-originated strings rendered in alert messages
**File:** `GlobalAlertCenter.tsx:85`, `GlobalAlertCenter.tsx:102`, `GlobalAlertCenter.tsx:121`
**Severity:** MEDIUM

Alert messages are constructed from WebSocket-originated fields (`newest.target_type`, `ev.action`, `ev.target_id`, `ev.entry_id`, `droneId`, `trans.mode`, `trans.reason`) without sanitization before rendering into JSX text nodes.

React text node rendering is inherently safe from script injection. However, a compromised or malicious backend could craft `target_type`, `reason`, or `trans.mode` values to contain misleading operator-visible text (e.g., "APPROVE ALL" or "AUTH LEVEL: ELEVATED"), constituting a UI redress / content injection attack against the operator. In a system where operator decisions have kinetic consequences, this is a meaningful risk.

**Recommendation:** Sanitize or truncate server-provided strings before embedding in alert messages. Apply a max-length cap (e.g., 64 chars) and strip non-printable characters:

```ts
function safeStr(s: unknown, maxLen = 64): string {
  if (typeof s !== 'string') return String(s ?? '?');
  return s.replace(/[^\x20-\x7E]/g, '').slice(0, maxLen);
}
```

---

### MEDIUM-2 — `entry.id` sent as WebSocket action parameter without frontend validation
**File:** `FloatingStrikeBoard.tsx:69`, `FloatingStrikeBoard.tsx:77`, `FloatingStrikeBoard.tsx:85`
**Severity:** MEDIUM

`entry.id` originates from the server (`StrikeEntry` interface, `id: string`) and is forwarded back as `entry_id` in WebSocket action payloads without format validation. If a buggy or malicious server sends a crafted `id` (excessively long, special characters, unexpected format), it gets forwarded verbatim.

**Risk:** Low exploitability since an attacker would need to compromise the backend first. However, this is a defense-in-depth gap.

**Recommendation:**
```ts
const UUID_RE = /^[0-9a-f-]{8,36}$/i;
function isSafeId(id: string): boolean {
  return UUID_RE.test(id) && id.length <= 36;
}
// Guard all three approval buttons before sendMessage calls
if (isSafeId(entry.id)) sendMessage({ action: 'approve_nomination', entry_id: entry.id, ... });
```

---

### LOW-1 — `makeId()` uses `Math.random()` — not cryptographically secure
**File:** `GlobalAlertCenter.tsx:33-35`
**Severity:** LOW

Alert IDs are client-side only and used solely as React `key` props. `Math.random()` is acceptable for this use case. With only 7 base-36 characters (~36 bits), collision probability is negligible given the 20-alert cap.

**Risk:** Negligible. No action required.

---

### LOW-2 — Hardcoded `rationale` strings in nomination actions reduce audit trail quality
**File:** `FloatingStrikeBoard.tsx:69`, `FloatingStrikeBoard.tsx:77`, `FloatingStrikeBoard.tsx:85`
**Severity:** LOW

All overlay-originated decisions write static strings ("Approved via overlay", "Rejected via overlay", "Retasked via overlay") to the `rationale` field, making it impossible to distinguish deliberate decisions from accidental clicks in the audit trail.

**Risk:** Audit trail degradation. Not a direct security vulnerability.

**Recommendation:** Add a timestamp: `rationale: \`Approved via overlay at ${new Date().toISOString()}\`` — though `audit_trail.py` likely adds server-side timestamps independently.

---

### LOW-3 — Event bridge forwards payload objects without field-level validation
**File:** `App.tsx:35-47`
**Severity:** LOW (well-mitigated, but noted)

The `grid_sentinel:send` bridge correctly allowlists which `action` values can be dispatched. However, the full `detail` object is forwarded wholesale — additional payload fields (`drone_id`, `target_id`, coordinates) are not validated. A script injected into the Cesium context could fire events with allowlisted actions but crafted numeric payloads.

**Risk:** Low — requires a separate injection vector within Cesium first. The allowlist effectively prevents action injection.

**Recommendation:** The current implementation is a good security improvement. For defense-in-depth, validate that numeric fields are integers within expected ranges before forwarding.

---

## Positive Security Observations

- **Safe JSX rendering** used throughout. All server data renders through text nodes with no unsafe HTML injection patterns.
- **Action allowlist on event bridge** (`App.tsx:35`) is well-implemented. The comment "Only allowlisted actions may be dispatched via the event bridge" shows clear security intent.
- **Alert cap of 20** (`GlobalAlertCenter.tsx:61`) prevents unbounded memory growth from a flooding backend.
- **No secrets, tokens, or credentials** present in any reviewed file.
- **No dynamic code execution** in any reviewed file.
- **Type-safe Zustand store access** via typed selectors reduces mutation surface.

---

## OWASP Top 10 Checklist

| Category | Status | Notes |
|----------|--------|-------|
| A01 Broken Access Control | PASS | No access control logic in these UI components |
| A02 Cryptographic Failures | PASS | No crypto in scope |
| A03 Injection | PASS (with caveat) | Safe rendering used; content injection possible via MEDIUM-1 |
| A04 Insecure Design | PASS | Alert center is display-only; strike board actions gated by backend |
| A05 Security Misconfiguration | PASS | No config in scope |
| A06 Vulnerable Components | N/A | Blueprint.js components; no known CVEs in scope |
| A07 Auth Failures | PASS | Auth handled at WebSocket layer (auth.py), not in these components |
| A08 Software/Data Integrity | LOW-3 | Event bridge payload not schema-validated |
| A09 Logging/Monitoring | LOW-2 | Hardcoded rationale strings reduce audit trail quality |
| A10 SSRF | PASS | No outbound requests from these components |

---

## Action Items

| ID | Severity | File | Action |
|----|----------|------|--------|
| MEDIUM-1 | MEDIUM | `GlobalAlertCenter.tsx` | Add `safeStr()` sanitizer for server-provided strings in alert message templates |
| MEDIUM-2 | MEDIUM | `FloatingStrikeBoard.tsx` | Validate `entry.id` against UUID pattern before sending as `entry_id` |
| LOW-2 | LOW | `FloatingStrikeBoard.tsx` | Improve `rationale` strings to include timestamps |
| LOW-3 | LOW | `App.tsx` | Optional: validate numeric payload fields on event bridge before forwarding |
