"""
AMPS — Aviation Mission Planning System.

Stub: schedules an aviation strike-package mission. Returns a route-of-flight
ack with crew brief / divert / weapon-config metadata.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

import structlog

from .base import EffectorAck, _now_ms

logger = structlog.get_logger()


@dataclass(frozen=True)
class AviationMissionRequest:
    target_id: int
    target_lat: float
    target_lon: float
    platform: Literal["F-35", "F-15E", "MQ-9", "AH-64", "B-21"] = "F-15E"
    weapon: Literal["GBU-31_JDAM", "GBU-39_SDB", "AGM-114_HELLFIRE", "AGM-158_JASSM"] = "GBU-31_JDAM"
    target_window_minutes: int = 30


class AmpsStub:
    name = "AMPS"

    def dispatch(self, req: AviationMissionRequest) -> EffectorAck:
        sent_ms = _now_ms()
        ack_ms = sent_ms + random.randint(900, 2400)  # AMPS planning round-trip ~1-2s for ack
        accepted = req.target_window_minutes > 0 and req.target_id > 0
        mission_id = f"ATO-{random.randint(0, 0xFFFFFFFF):08X}"
        detail = (
            f"AMPS scheduled {req.platform} with {req.weapon} on TGT#{req.target_id}, "
            f"window {req.target_window_minutes}min."
        ) if accepted else "AMPS rejected (zero window)."
        logger.info(
            "amps_schedule",
            mission_id=mission_id,
            target_id=req.target_id,
            platform=req.platform,
            weapon=req.weapon,
            accepted=accepted,
        )
        return EffectorAck(
            effector=self.name,
            accepted=accepted,
            mission_id=mission_id,
            sent_at_ms=sent_ms,
            ack_at_ms=ack_ms,
            detail=detail,
        )
