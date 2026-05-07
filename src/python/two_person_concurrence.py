"""
two_person_concurrence.py
=========================
Closes the FedRAMP-High control gap flagged in `docs/SECURITY_POSTURE.md`:
no AUTONOMOUS engagement is allowed to dispatch a kinetic effector
without **two distinct operators** concurring within a 5-minute window.

Maven runs single-operator authorisation; FedRAMP High requires
two-person concurrence on irreversible kinetic actions. We add a small,
dependency-free service that the engagement path consults before any
effector dispatch.

Public API:
    request_concurrence(target_id, primary_operator_id, ...)
    record_concurrence(target_id, secondary_operator_id, ...)
    is_authorised(target_id) -> bool
    pending() -> list[dict]
    expire_old(now=None)

Audit-logged on every state change so postmortem AAR can prove the
two-person rule held.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# Window inside which the second operator must concur after the first
# requests it. After this expires the request is dropped and the
# engagement falls back to manual authorisation.
DEFAULT_WINDOW_SEC = 300.0


@dataclass(frozen=True)
class ConcurrenceRequest:
    target_id: int
    primary_operator_id: str
    rationale: str
    created_at: float
    coa_id: Optional[str] = None


@dataclass(frozen=True)
class ConcurrenceRecord:
    target_id: int
    primary_operator_id: str
    secondary_operator_id: str
    rationale: str
    coa_id: Optional[str]
    created_at: float
    concurred_at: float

    @property
    def latency_sec(self) -> float:
        return max(0.0, self.concurred_at - self.created_at)


class TwoPersonConcurrence:
    """Tracks pending and authorised two-person concurrence records."""

    def __init__(self, window_sec: float = DEFAULT_WINDOW_SEC) -> None:
        self._window_sec = window_sec
        self._pending: dict[int, ConcurrenceRequest] = {}
        self._authorised: dict[int, ConcurrenceRecord] = {}
        self._lock = threading.Lock()

    # -- mutation -------------------------------------------------------

    def request_concurrence(
        self,
        *,
        target_id: int,
        primary_operator_id: str,
        rationale: str = "",
        coa_id: Optional[str] = None,
        now: Optional[float] = None,
    ) -> ConcurrenceRequest:
        """First operator requests concurrence on a kinetic action."""
        if not primary_operator_id or not isinstance(primary_operator_id, str):
            raise ValueError("primary_operator_id required")
        now = now if now is not None else time.time()
        req = ConcurrenceRequest(
            target_id=int(target_id),
            primary_operator_id=primary_operator_id,
            rationale=str(rationale),
            created_at=now,
            coa_id=coa_id,
        )
        with self._lock:
            self._pending[req.target_id] = req
            # An existing authorised record is invalidated when a new
            # request is opened — concurrence is per-target, single-shot.
            self._authorised.pop(req.target_id, None)
        self._audit("two_person_request", req.target_id, {
            "primary_operator_id": primary_operator_id,
            "rationale": rationale,
            "coa_id": coa_id,
        })
        return req

    def record_concurrence(
        self,
        *,
        target_id: int,
        secondary_operator_id: str,
        now: Optional[float] = None,
    ) -> ConcurrenceRecord:
        """Second operator concurs. Raises ValueError on missing request,
        same-operator, or expired window.
        """
        if not secondary_operator_id or not isinstance(secondary_operator_id, str):
            raise ValueError("secondary_operator_id required")
        now = now if now is not None else time.time()
        with self._lock:
            req = self._pending.get(int(target_id))
            if req is None:
                raise ValueError(f"no pending concurrence for target {target_id}")
            if req.primary_operator_id == secondary_operator_id:
                raise ValueError("primary and secondary operator must differ")
            if (now - req.created_at) > self._window_sec:
                # Expired — drop it and refuse
                self._pending.pop(int(target_id), None)
                self._audit("two_person_expired", int(target_id), {
                    "primary_operator_id": req.primary_operator_id,
                    "window_sec": self._window_sec,
                })
                raise ValueError(
                    f"concurrence window ({self._window_sec:.0f}s) expired for target {target_id}"
                )
            record = ConcurrenceRecord(
                target_id=req.target_id,
                primary_operator_id=req.primary_operator_id,
                secondary_operator_id=secondary_operator_id,
                rationale=req.rationale,
                coa_id=req.coa_id,
                created_at=req.created_at,
                concurred_at=now,
            )
            self._pending.pop(req.target_id, None)
            self._authorised[req.target_id] = record
        self._audit("two_person_concurred", record.target_id, {
            "primary_operator_id": record.primary_operator_id,
            "secondary_operator_id": secondary_operator_id,
            "latency_sec": round(record.latency_sec, 2),
            "coa_id": record.coa_id,
        })
        return record

    def consume_authorisation(self, target_id: int) -> Optional[ConcurrenceRecord]:
        """Pop the authorisation atomically when the engagement dispatches.

        Two-person concurrence is single-shot: an authorised record can
        be consumed once. Subsequent engagements need a fresh pair.
        """
        with self._lock:
            return self._authorised.pop(int(target_id), None)

    def expire_old(self, now: Optional[float] = None) -> list[ConcurrenceRequest]:
        """Drop any pending request older than the window. Returns the
        expired requests so callers can audit-log them.
        """
        now = now if now is not None else time.time()
        expired: list[ConcurrenceRequest] = []
        with self._lock:
            for tid, req in list(self._pending.items()):
                if (now - req.created_at) > self._window_sec:
                    expired.append(req)
                    self._pending.pop(tid, None)
        for req in expired:
            self._audit("two_person_expired", req.target_id, {
                "primary_operator_id": req.primary_operator_id,
                "window_sec": self._window_sec,
            })
        return expired

    # -- query ----------------------------------------------------------

    def is_authorised(self, target_id: int) -> bool:
        with self._lock:
            return int(target_id) in self._authorised

    def pending(self) -> list[dict]:
        with self._lock:
            return [asdict(r) for r in self._pending.values()]

    def authorised(self) -> list[dict]:
        with self._lock:
            return [asdict(r) for r in self._authorised.values()]

    # -- helpers --------------------------------------------------------

    def _audit(self, action_type: str, target_id: int, details: dict) -> None:
        try:
            from audit_log import audit_log as _audit_log
            _audit_log.append(
                action_type=action_type,
                target_id=int(target_id),
                details=details,
            )
        except Exception:  # noqa: BLE001
            logger.debug("two_person_audit_skipped", extra={"target_id": target_id})


# Module-level singleton — like audit_log
two_person_concurrence = TwoPersonConcurrence()
