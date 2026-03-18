from enum import Enum


class AssetStatus(str, Enum):
    idle = "idle"
    reserved = "reserved"
    launching = "launching"
    transiting = "transiting"
    on_task = "on_task"
    returning = "returning"
    landing = "landing"
    charging = "charging"
    offline = "offline"
    degraded = "degraded"
    lost = "lost"
    maintenance = "maintenance"


class AssetMode(str, Enum):
    manual = "manual"
    guided = "guided"
    auto = "auto"
    rtl = "rtl"
    hold = "hold"
    simulated = "simulated"


class AssetHealth(str, Enum):
    nominal = "nominal"
    warning = "warning"
    critical = "critical"
    failed = "failed"


class MissionType(str, Enum):
    surveillance = "surveillance"
    delivery = "delivery"
    inspection = "inspection"
    search_rescue = "search_rescue"
    rebalance = "rebalance"
    custom = "custom"


class MissionState(str, Enum):
    draft = "draft"
    proposed = "proposed"
    approved = "approved"
    queued = "queued"
    active = "active"
    paused = "paused"
    completed = "completed"
    aborted = "aborted"
    failed = "failed"
    archived = "archived"


class Priority(str, Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class TaskType(str, Enum):
    goto = "goto"
    loiter = "loiter"
    survey = "survey"
    deliver = "deliver"
    inspect = "inspect"
    return_home = "return_home"
    reposition = "reposition"
    custom = "custom"


class TaskState(str, Enum):
    waiting = "waiting"
    ready = "ready"
    assigned = "assigned"
    transit = "transit"
    active = "active"
    blocked = "blocked"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TargetKind(str, Enum):
    point = "point"
    area = "area"
    route = "route"
    asset = "asset"


class CommandType(str, Enum):
    move_to = "move_to"
    hold_position = "hold_position"
    return_home = "return_home"
    launch = "launch"
    land = "land"
    start_task = "start_task"
    abort_task = "abort_task"
    set_mode = "set_mode"
    start_mission = "start_mission"
    pause_mission = "pause_mission"
    abort_mission = "abort_mission"


class CommandTargetType(str, Enum):
    asset = "asset"
    mission = "mission"
    task = "task"


class CommandState(str, Enum):
    proposed = "proposed"
    validated = "validated"
    rejected = "rejected"
    approved = "approved"
    queued = "queued"
    sent = "sent"
    acknowledged = "acknowledged"
    active = "active"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    expired = "expired"


class ReservationPhase(str, Enum):
    idle = "idle"
    launch = "launch"
    transit = "transit"
    hold = "hold"
    task_execution = "task_execution"
    return_ = "return"
    recovery = "recovery"
    charging = "charging"
    maintenance = "maintenance"


class ReservationStatus(str, Enum):
    planned = "planned"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    conflict = "conflict"


class ReservationSource(str, Enum):
    planned = "planned"
    predicted = "predicted"
    actual = "actual"


class AlertType(str, Enum):
    link_loss = "link_loss"
    low_battery = "low_battery"
    stale_telemetry = "stale_telemetry"
    mission_delay = "mission_delay"
    geofence_violation = "geofence_violation"
    command_failed = "command_failed"
    conflict_detected = "conflict_detected"
    health_degraded = "health_degraded"
    system_error = "system_error"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertState(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    cleared = "cleared"


class AlertSourceType(str, Enum):
    asset = "asset"
    mission = "mission"
    task = "task"
    command = "command"
    system = "system"
