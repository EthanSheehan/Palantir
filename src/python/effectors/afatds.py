"""
AFATDS — Advanced Field Artillery Tactical Data System.

Stub: accepts a fire-mission request shaped after the real AFATDS Tactical
Fire Direction System message format. Produces a realistic-looking
acknowledgement with a TFD-style mission ID (FM-YYDDDHHMMSS) and a sub-second
ack latency to match what an artillery battery would publish.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Literal

import structlog

from .base import EffectorAck, _now_ms

logger = structlog.get_logger()


@dataclass(frozen=True)
class FireMissionRequest:
    target_id: int
    target_lat: float
    target_lon: float
    target_type: str
    munition: Literal["155MM_HE", "155MM_EXC", "GMLRS_AW", "ATACMS"] = "155MM_HE"
    rounds: int = 4
    fire_for_effect: bool = True
    rationale: str = ""


class AfatdsStub:
    name = "AFATDS"

    def dispatch(self, req: FireMissionRequest) -> EffectorAck:
        sent_ms = _now_ms()
        # Mission ID format used by real-world TFD: FM-YYDDDHHMMSS-<seq>
        t = time.gmtime()
        seq = random.randint(1000, 9999)
        mission_id = f"FM-{t.tm_year % 100:02d}{t.tm_yday:03d}{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}-{seq}"
        # AFATDS typically acks in 200–800ms over JVMF/SADL
        ack_ms = sent_ms + random.randint(180, 820)
        accepted = req.rounds > 0 and req.target_id > 0
        detail = (
            f"FM accepted: {req.munition} x {req.rounds} on TGT#{req.target_id} ({req.target_type}). "
            f"FFE={req.fire_for_effect}."
        ) if accepted else "FM rejected: invalid request."
        logger.info("afatds_fire_mission", mission_id=mission_id, target_id=req.target_id, accepted=accepted)
        return EffectorAck(
            effector=self.name,
            accepted=accepted,
            mission_id=mission_id,
            sent_at_ms=sent_ms,
            ack_at_ms=ack_ms,
            detail=detail,
            nato_msg_id=f"K02.1-FFI-{seq}",
        )
