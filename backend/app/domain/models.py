from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid

from .enums import (
    AssetStatus, AssetMode, AssetHealth,
    MissionType, MissionState, Priority,
    TaskType, TaskState, TargetKind,
    CommandType, CommandTargetType, CommandState,
    ReservationPhase, ReservationStatus, ReservationSource,
    AlertType, AlertSeverity, AlertState, AlertSourceType,
)


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Nested value objects ──

class Position(BaseModel):
    lon: float = 0.0
    lat: float = 0.0
    alt_m: float = 0.0


class Velocity(BaseModel):
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    vz_mps: float = 0.0


class TaskTarget(BaseModel):
    kind: TargetKind = TargetKind.point
    data: dict[str, Any] = Field(default_factory=dict)


class MissionConstraints(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    geofences: list[str] = Field(default_factory=list)
    max_assets: Optional[int] = None
    required_capabilities: list[str] = Field(default_factory=list)


class TaskConstraints(BaseModel):
    required_capabilities: list[str] = Field(default_factory=list)
    min_battery_pct: Optional[float] = None
    geofence_ids: list[str] = Field(default_factory=list)


# ── Core entities ──

class Asset(BaseModel):
    id: str = Field(default_factory=lambda: _gen_id("ast"))
    name: str = ""
    type: str = "quadrotor"
    status: AssetStatus = AssetStatus.idle
    mode: AssetMode = AssetMode.simulated
    position: Position = Field(default_factory=Position)
    velocity: Velocity = Field(default_factory=Velocity)
    heading_deg: float = 0.0
    battery_pct: float = 100.0
    link_quality: float = 1.0
    health: AssetHealth = AssetHealth.nominal
    payload_state: str = ""
    home_location: Position = Field(default_factory=Position)
    assigned_mission_id: Optional[str] = None
    assigned_task_id: Optional[str] = None
    last_telemetry_time: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    version: int = 1
    updated_at: str = Field(default_factory=_now)


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: _gen_id("msn"))
    name: str = ""
    type: MissionType = MissionType.custom
    priority: Priority = Priority.normal
    objective: str = ""
    state: MissionState = MissionState.draft
    created_at: str = Field(default_factory=_now)
    created_by: str = "operator"
    approved_by: Optional[str] = None
    constraints: MissionConstraints = Field(default_factory=MissionConstraints)
    assigned_asset_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    version: int = 1
    updated_at: str = Field(default_factory=_now)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: _gen_id("tsk"))
    mission_id: str = ""
    type: TaskType = TaskType.goto
    priority: Priority = Priority.normal
    state: TaskState = TaskState.waiting
    target: TaskTarget = Field(default_factory=TaskTarget)
    service_time_sec: Optional[float] = None
    earliest_start: Optional[str] = None
    latest_finish: Optional[str] = None
    assigned_asset_ids: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)
    version: int = 1
    updated_at: str = Field(default_factory=_now)


class Command(BaseModel):
    id: str = Field(default_factory=lambda: _gen_id("cmd"))
    type: CommandType = CommandType.move_to
    target_type: CommandTargetType = CommandTargetType.asset
    target_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    state: CommandState = CommandState.proposed
    created_at: str = Field(default_factory=_now)
    created_by: str = "operator"
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    dispatched_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    completed_at: Optional[str] = None
    failure_reason: Optional[str] = None
    correlation_id: Optional[str] = None
    version: int = 1


class TimelineReservation(BaseModel):
    id: str = Field(default_factory=lambda: _gen_id("res"))
    asset_id: str = ""
    mission_id: Optional[str] = None
    task_id: Optional[str] = None
    phase: ReservationPhase = ReservationPhase.idle
    start_time: str = Field(default_factory=_now)
    end_time: str = Field(default_factory=_now)
    status: ReservationStatus = ReservationStatus.planned
    source: ReservationSource = ReservationSource.planned


class Alert(BaseModel):
    id: str = Field(default_factory=lambda: _gen_id("alt"))
    type: AlertType = AlertType.system_error
    severity: AlertSeverity = AlertSeverity.info
    state: AlertState = AlertState.open
    created_at: str = Field(default_factory=_now)
    source_type: AlertSourceType = AlertSourceType.system
    source_id: str = ""
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Domain event ──

class DomainEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: str = ""
    timestamp: str = Field(default_factory=_now)
    source_service: str = ""
    entity_type: str = ""
    entity_id: str = ""
    version: int = 1
    payload: dict[str, Any] = Field(default_factory=dict)
