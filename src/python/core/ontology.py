"""
core/ontology.py
================
Shared data ontology for the Multi-Agent C2 System (Project Antigravity).

All agents interact through these Pydantic models, ensuring a consistent
world-view across the ISR Observer, Strategy Analyst, Tactical Planner,
and Effectors Agent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DetectionType(str, Enum):
    """Classification of a detected entity."""

    VEHICLE = "vehicle"
    PERSONNEL = "personnel"
    LAUNCHER = "launcher"  # e.g., TEL (Transporter Erector Launcher)
    STRUCTURE = "structure"
    AIRCRAFT = "aircraft"
    NAVAL = "naval"
    UNKNOWN = "unknown"


class IdentityClassification(str, Enum):
    """Standard identity classification (MIL-STD-2525)."""

    HOSTILE = "hostile"
    SUSPECT = "suspect"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    UNKNOWN = "unknown"


class SensorType(str, Enum):
    """Type of ISR sensor that produced a detection."""

    EO_IR = "EO/IR"  # Electro-Optical / Infrared
    SAR = "SAR"  # Synthetic Aperture Radar
    SIGINT = "SIGINT"  # Signals Intelligence
    HUMINT = "HUMINT"  # Human Intelligence
    AIS = "AIS"  # Automatic Identification System
    GMTI = "GMTI"  # Ground Moving Target Indicator
    FMV = "FMV"  # Full Motion Video


class ROEAction(str, Enum):
    """Actions permitted or denied by a Rule of Engagement."""

    ENGAGE = "engage"
    OBSERVE_ONLY = "observe_only"
    WITHDRAW = "withdraw"
    REPORT = "report"


class SensorStatus(str, Enum):
    """Operational readiness of an ISR sensor asset."""

    AVAILABLE = "available"
    TASKED = "tasked"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------


class Location(BaseModel):
    """WGS-84 geographic coordinate."""

    latitude: float = Field(..., ge=-90, le=90, description="Degrees latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Degrees longitude")
    altitude_m: Optional[float] = Field(None, description="Altitude in metres (MSL)")


class Detection(BaseModel):
    """
    A single detection produced by the ISR Observer.
    This is the primary input to the Strategy Analyst.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detection_type: DetectionType
    identity: IdentityClassification
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence 0-1")
    location: Location
    sensor: SensorType
    description: str = Field("", description="Free-text analyst notes")


class FriendlyForce(BaseModel):
    """A friendly unit or asset."""

    id: str
    name: str
    unit_type: str  # e.g., "Infantry Platoon", "MQ-9 Reaper"
    location: Location


class RuleOfEngagement(BaseModel):
    """A single ROE constraint."""

    id: str
    description: str
    permitted_action: ROEAction
    min_confidence: float = Field(0.8, ge=0.0, le=1.0, description="Minimum confidence to act")
    min_distance_friendly_m: float = Field(500.0, ge=0.0, description="Minimum metres from friendly forces")
    applicable_identities: list[IdentityClassification] = Field(
        default_factory=lambda: [IdentityClassification.HOSTILE]
    )


# ---------------------------------------------------------------------------
# Agent Outputs
# ---------------------------------------------------------------------------


class TaskingRequest(BaseModel):
    """
    Issued by the Strategy Analyst when a detection is ambiguous.
    Requests the ISR Observer to task a secondary sensor for confirmation.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    detection_id: str
    requested_sensor: SensorType
    reason: str


class ActionableTarget(BaseModel):
    """
    A validated, ROE-compliant target moved to the Strike Board
    for the Tactical Planner.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    detection: Detection
    priority: int = Field(..., ge=1, le=10, description="Threat priority 1 (low) – 10 (critical)")
    reasoning_trace: str = Field(..., description="Explanation of why this target is actionable")
    nearest_friendly_id: str
    nearest_friendly_distance_m: float
    recommended_action: ROEAction
