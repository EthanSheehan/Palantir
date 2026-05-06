"""
effectors package
=================
Mock dispatch endpoints for the canonical DoD weapons-systems Maven talks to:

- AFATDS  : Advanced Field Artillery Tactical Data System
- JREAP   : Joint Range Extension Application Protocol (weapons routing)
- JADOCS  : Joint Automated Deep Operations Coordination System
- AMPS    : Aviation Mission Planning System

Each stub accepts a realistic message schema, logs the dispatch with timing,
and returns an acknowledgement. Effectors are *intentionally not real* — the
demo realism is in the message shapes and timing, not in actually controlling
munitions. We will not build these against live systems.
"""
from .afatds import AfatdsStub
from .jreap import JreapStub
from .jadocs import JadocsStub
from .amps import AmpsStub
from .base import EffectorAck

__all__ = ["AfatdsStub", "JreapStub", "JadocsStub", "AmpsStub", "EffectorAck"]
