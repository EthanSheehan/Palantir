---
tags: [grid_sentinel, security, posture, IL5, IL6, FedRAMP]
---
# Grid-Sentinel Security Posture

*Generated 2026-05-07 · Companion to `docs/PROFESSIONAL_LEVEL_BLUEPRINT.md`*

This document tracks Grid-Sentinel's current security controls against the
control families that matter for **DISA Impact Level 5 / 6** and
**FedRAMP High** — the certification levels Maven Smart System operates
under in production deployments. The intent is honest assessment, not a
checklist tick: we list what's already implemented, what's partially
implemented, and what would have to be built to achieve the corresponding
control.

## Summary

| Posture target | Status | Headline gap |
|---|---|---|
| DISA Impact Level 5 (IL5) | partially met | FIPS-140-3 validated crypto, separated auth domain |
| DISA Impact Level 6 (IL6) — SECRET | not met | Cross-domain solution, NSA Type 1 crypto, hardware-attested boot |
| FedRAMP High | partially met | Continuous monitoring (CM-3, CM-8), formal incident-response plan |
| NIST 800-53 Rev 5 baseline | partially met | See per-family summary below |

Grid-Sentinel is **functionally** capable of operating at IL5 / IL6 once
the gaps below are closed. None of them are architectural rewrites — most
are configuration, policy, or third-party integration work.

## What's already implemented

### Identity, authentication & authorization
- **`src/python/auth.py`** — JWT-based WebSocket authentication with
  configurable signing secrets, token expiry, audience claims.
- **`src/python/rbac.py`** — Role-based access control with four tiers
  (OBSERVER / OPERATOR / COMMANDER / ADMIN) and `AUTH_DISABLED` env var
  for development bypass. Per-action permission matrix in
  `websocket_handlers.py`.
- **Persona-aware classification** — `set_persona` action +
  `_filter_for_persona()` strip CUI/SECRET fields per WebSocket client
  based on declared classification tier
  (`src/python/api_main.py:_FIELD_CLASSIFICATION`). Beyond-Maven feature
  — Maven runs single-tier per deployment; we filter live.

### Transport & input safety
- **`src/python/tls_support.py`** — TLS/SSL configuration with
  certificate validation and origin allow-listing (localhost bypass for
  development). Uses Python `ssl` module, OpenSSL upstream.
- **`src/python/llm_sanitizer.py`** — LLM prompt-injection defence;
  strips known injection patterns from operator queries before they're
  forwarded to a model.
- **WebSocket size guards & rate limiting** — message size cap and
  per-client token-bucket rate limit applied in
  `websocket_handlers.handle_payload`.

### Auditing & non-repudiation
- **`src/python/audit_log.py`** — Tamper-evident SHA-256 hash chain.
  Every record includes `prev_hash` + `record_hash`; `verify_chain()`
  detects any retroactive mutation. Records carry `autonomy_level`,
  `target_id`, `drone_id`, `operator_id`, `sensor_evidence`, `details`.
- **Audit-log integrations** — Verification state transitions,
  effector dispatches (with NATO message ID + ack latency), engagement
  outcomes, COA authorisations (with ROE rule attribution), nomination
  approve/reject/retask, all flow through `audit_log.append`.
- **`src/python/audit_trail.py`** — alias module exposing the same
  AuditLog for legacy import paths.

### AI safety & explainability
- **`src/python/explainability.py`** — Structured rationale for every
  AI recommendation; provider/model/tokens captured with each LLM call
  (visible in `ModelHubBadge`).
- **`src/python/confidence_gate.py`** — Confidence-based decision gate
  blocking auto-engagement below operator-configurable thresholds.
- **`src/python/override_capture.py`** — Records every operator
  override with reason code + free-text rationale for AAR.
- **`src/python/audit_log` integration with reflective AI** — the
  `self_critic` agent (`/critic`) periodically scans the audit chain
  for COA churn / repeated-rejection patterns.

### Reliability
- **`src/python/checkpoint.py` + `persistence.py`** — SQLite-backed
  mission checkpoint and restart capability.
- **`src/python/aar_engine.py`** — Post-mission After Action Review
  engine reads the audit chain and produces structured reports.
- **`src/python/lost_link.py`** — Per-drone lost-link behaviour
  (LOITER / RTB / SAFE_LAND / CONTINUE) for resilience under degraded
  comms.
- **`src/python/comms_sim.py`** — Communication degradation simulation
  for AAR / training (FULL / CONTESTED / DENIED).

### Observability
- **`src/python/metrics.py`** — Prometheus text-format `/metrics`
  endpoint with histograms / gauges / counters for tick duration,
  client count, detection events, HITL approvals, F2T2EA per-stage SLA
  histograms (FIND/FIX/TRACK/TARGET/ENGAGE/ASSESS).
- **`src/python/event_logger.py`** — Async JSONL event logging with
  daily rotation, suitable for SIEM ingest.

## What's partially implemented

| Control | Status | What's missing |
|---|---|---|
| Continuous monitoring (CM-3, CM-8) | partial | `metrics.py` exposes a Prometheus endpoint, but no Grafana / SIEM dashboards committed. No automated drift detection. |
| Configuration management (CM-2) | partial | `theaters/*.yaml` + `roe/*.yaml` are version-controlled, but no signed-baseline workflow. |
| Boundary protection (SC-7) | partial | `tls_support.py` covers WebSocket TLS; no formal network segmentation diagram or DMZ deployment recipe. |
| Encryption at rest (SC-28) | partial | SQLite checkpoints are plaintext on disk. No key-management for stored audit chain. |
| Vulnerability scanning (RA-5) | implemented | `pip-audit`, `npm audit --audit-level=high`, `bandit` SAST, `trufflehog` verified-secrets scan all in `.github/workflows/security.yml` (push + weekly cron). SARIF uploaded to GitHub Security tab. |
| Incident response (IR-2 .. IR-8) | not implemented | No documented IR playbook, no IR plan in repo. |
| System backup (CP-9) | partial | `checkpoint.py` enables operational restart; no scheduled off-host backup. |

## What's not implemented (closure work for IL5 / IL6 / FedRAMP High)

### IL5-specific
- **FIPS-140-3 validated cryptography.** Switch JWT signing and TLS
  cipher suite to FIPS-validated providers (e.g. OpenSSL FIPS provider).
  Currently uses default Python `cryptography` defaults.
- **Hardware Security Module (HSM) integration** for JWT signing keys.
- **DoD CAC / PIV smart-card auth** as a JWT alternative.
- **`STIG-compliant` container hardening** — Dockerfile and base image
  STIG-pass per CAT-I findings.
- **Auth domain separation** — operator and admin auth must terminate
  on separate identity providers per DISA SRG.

### IL6-specific (SECRET)
- **NSA Type 1 cryptography** for SECRET-tagged data — out of reach for
  open-source software; would require partnership.
- **Cross-domain solution (CDS)** — formal accreditation as a one-way
  guard between SIPR and JWICS / NIPR.
- **Hardware-attested boot** + measured launch environment.
- **Compartmented controls (CO-MAR)** — per-compartment access control,
  beyond the existing UNCLASS/CUI/SECRET tiering.
- **TEMPEST / red-black separation** at the deployment platform level.

### FedRAMP High (CIA: H/H/H)
- **Two-person concurrence** for any AUTONOMOUS-level engagement.
  Confidence gate exists; two-person concurrence does not.
- **Continuous monitoring** with quarterly POAM updates.
- **3-year audit log retention** — currently in-memory + SQLite; needs
  archival storage.
- **System security plan (SSP)** + **incident-response plan (IRP)** —
  documents not in repo.
- **Boundary scanning** with authenticated scans of the OS image.

## CI verification of posture-relevant controls

`.github/workflows/test.yml` (since iteration 15 of the beyond-Maven push)
runs the following on every push:

- Multi-Python (3.11/3.12/3.13) `pytest` with coverage threshold 70%
  — verifies the audit_log hash-chain tests, persona-filter tests,
  ROE-rule attribution tests still pass.
- `ruff check src/python/` — minimum lint floor.
- Frontend `tsc --noEmit` typecheck and full Vite build artifact.
- AsyncAPI YAML parse validation — keeps the WebSocket protocol
  contract honest.

**Update (iteration 19):** `.github/workflows/security.yml` now runs:

- `pip-audit` against `requirements.txt` with SARIF upload
- `npm audit --audit-level=high` against `src/frontend-react/`
- `bandit` static analysis on `src/python/` with SARIF upload
- `trufflehog` verified-secrets scan on every push + weekly cron

Findings appear in the GitHub Security tab. Weekly cron (Sun 04:30 UTC)
re-runs on the codebase as-is, so newly disclosed CVEs surface even
without a code change.

Still TODO: `trivy fs` against a built container image (no Dockerfile in
repo yet); `osv-scanner` for cross-ecosystem coverage; CODEOWNERS-gated
review on changes to `.github/workflows/`.

## References

- DoD Cloud Computing Security Requirements Guide (SRG) v1r4 — IL5/IL6
- NIST SP 800-53 Rev 5 control catalog
- FedRAMP High baseline (rev5)
- DISA STIG library
- *Inside Palantir's Maven Smart System* (Spatial Intelligence) — for
  comparable IL5/IL6 deployment context
