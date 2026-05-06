"""
JADOCS — Joint Automated Deep Operations Coordination System.

Stub: registers a deep-fire coordination request for cross-domain deconfliction.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

import structlog

from .base import EffectorAck, _now_ms

logger = structlog.get_logger()


@dataclass(frozen=True)
class DeepFireRequest:
    target_id: int
    target_lat: float
    target_lon: float
    desired_effect: Literal["NEUTRALIZE", "DEGRADE", "DESTROY"] = "DESTROY"
    coordination_window_min: int = 15


class JadocsStub:
    name = "JADOCS"

    def dispatch(self, req: DeepFireRequest) -> EffectorAck:
        sent_ms = _now_ms()
        ack_ms = sent_ms + random.randint(420, 1500)  # JADOCS coordinates across domains, slower ack
        accepted = req.coordination_window_min >= 0 and req.target_id > 0
        mission_id = f"DC-{random.randint(0, 0xFFFFFF):06X}"
        detail = (
            f"Deep-fire coord window {req.coordination_window_min}min for {req.desired_effect}."
        ) if accepted else "JADOCS rejected (invalid window)."
        logger.info(
            "jadocs_coordinate",
            mission_id=mission_id,
            target_id=req.target_id,
            effect=req.desired_effect,
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
