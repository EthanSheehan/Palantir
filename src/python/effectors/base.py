"""Common base + ack type for effector stubs."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EffectorAck:
    effector: str            # "AFATDS" | "JREAP" | "JADOCS" | "AMPS"
    accepted: bool
    mission_id: str
    sent_at_ms: int
    ack_at_ms: int
    detail: str = ""
    nato_msg_id: Optional[str] = None

    @property
    def latency_ms(self) -> int:
        return max(0, self.ack_at_ms - self.sent_at_ms)


def _now_ms() -> int:
    return int(time.time() * 1000)
