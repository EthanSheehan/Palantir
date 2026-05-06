"""
JREAP — Joint Range Extension Application Protocol.

Stub: forwards a target track to weapons via Link 16 / SATCOM relay.
Produces a J-series J3.2 (PPLI/Air Track) style ack.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

import structlog

from .base import EffectorAck, _now_ms

logger = structlog.get_logger()


@dataclass(frozen=True)
class TrackForwardRequest:
    target_id: int
    target_lat: float
    target_lon: float
    track_quality: int  # 0..15 per Link 16
    forward_to: Literal["AIR_OPS_CTR", "SHIPBOARD_CIWS", "GROUND_BAT"] = "AIR_OPS_CTR"


class JreapStub:
    name = "JREAP"

    def dispatch(self, req: TrackForwardRequest) -> EffectorAck:
        sent_ms = _now_ms()
        ack_ms = sent_ms + random.randint(60, 350)  # SATCOM relay ~ low hundreds of ms
        accepted = 0 <= req.track_quality <= 15 and req.target_id > 0
        mission_id = f"J32-{random.randint(0, 0xFFFF):04X}"
        detail = (
            f"J3.2 track relayed to {req.forward_to}, TQ={req.track_quality}."
        ) if accepted else "J3.2 rejected (bad TQ)."
        logger.info(
            "jreap_relay",
            mission_id=mission_id,
            target_id=req.target_id,
            forward_to=req.forward_to,
            accepted=accepted,
        )
        return EffectorAck(
            effector=self.name,
            accepted=accepted,
            mission_id=mission_id,
            sent_at_ms=sent_ms,
            ack_at_ms=ack_ms,
            detail=detail,
            nato_msg_id=f"L16-J3.2-{mission_id}",
        )
