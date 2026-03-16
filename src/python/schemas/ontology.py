from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class TargetClassification(str, Enum):
    TEL = "TEL" # Transporter Erector Launcher
    SAM = "SAM" # Surface-to-Air Missile site
    CP = "Command Post"
    UNKNOWN = "Unknown"

class SensorSource(str, Enum):
    UAV = "UAV"
    SATELLITE = "Satellite"
    SIGINT = "SIGINT"

class Detection(BaseModel):
    source: SensorSource = Field(..., description="The sensor that made the detection")
    lat: float = Field(..., description="Latitude of the detection")
    lon: float = Field(..., description="Longitude of the detection")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the classification")
    classification: TargetClassification = Field(..., description="Classified type of the object")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the detection")

class Track(BaseModel):
    track_id: str = Field(..., description="Unique identifier for the fused track")
    lat: float = Field(..., description="Fused latitude")
    lon: float = Field(..., description="Fused longitude")
    classification: TargetClassification = Field(..., description="Highest confidence classification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Highest confidence score among detections")
    detections: List[Detection] = Field(default_factory=list, description="Raw detections forming this track")
    is_high_priority: bool = Field(default=False, description="Flag indicating if this is a High-Priority Target")

class ISRObserverOutput(BaseModel):
    tracks: List[Track] = Field(..., description="List of fused tracks identified by the ISR Observer")
    alerts: List[str] = Field(default_factory=list, description="Immediate alerts for the Strategy Analyst regarding High-Priority Targets")

class Effector(BaseModel):
    effector_id: str = Field(..., description="Unique identifier for the effector asset")
    name: str = Field(..., description="Name of the effector (e.g., F-35, HIMARS, Cyber Team)")
    effector_type: str = Field(..., description="Kinetic or Non-Kinetic")
    status: str = Field(..., description="Availability status")

class CourseOfAction(BaseModel):
    coa_id: str = Field(..., description="Unique ID for this COA")
    coa_type: str = Field(..., description="fastest, highest_pk, or lowest_cost")
    target_track_id: str = Field(..., description="ID of the track to be engaged")
    effector: Effector = Field(..., description="The effector selected for this COA")
    time_to_target_minutes: float = Field(..., description="Estimated time to target in minutes")
    probability_of_kill: float = Field(..., ge=0.0, le=1.0, description="Estimated probability of kill (Pk)")
    munition_efficiency_cost: float = Field(..., description="Relative cost or efficiency metric of the munition")
    rationalization: str = Field(..., description="Reasoning string explaining why this effector was chosen")

class TacticalPlannerOutput(BaseModel):
    target_track_id: str = Field(..., description="ID of the track this planning is for")
    coas: List[CourseOfAction] = Field(..., description="List of the 3 generated COAs (Fastest, Highest Pk, Lowest Cost)")


# --- Performance Auditor Schemas ---

class EffectOutcome(str, Enum):
    DESTROYED = "Destroyed"
    DAMAGED = "Damaged"
    NO_EFFECT = "No Effect"
    UNKNOWN = "Unknown"

class BDAReport(BaseModel):
    """Post-strike Battle Damage Assessment from the Effectors Agent."""
    bda_id: str = Field(..., description="Unique identifier for this BDA report")
    target_track_id: str = Field(..., description="Track ID of the engaged target")
    coa_id: str = Field(..., description="COA ID that was executed")
    effect_achieved: EffectOutcome = Field(..., description="Observed outcome of the strike")
    post_strike_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the BDA assessment")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the BDA")
    notes: str = Field(default="", description="Additional BDA observations")

class StrategyNomination(BaseModel):
    """Original target nomination from the Strategy Analyst."""
    nomination_id: str = Field(..., description="Unique identifier for this nomination")
    target_track_id: str = Field(..., description="Track ID of the nominated target")
    predicted_effect: EffectOutcome = Field(..., description="Expected effect of the strike")
    predicted_pk: float = Field(..., ge=0.0, le=1.0, description="Predicted probability of kill at nomination time")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the nomination")

class DiscrepancyFlag(BaseModel):
    """Flag raised when a strike outcome does not match the predicted effect."""
    flag_id: str = Field(..., description="Unique identifier for this discrepancy flag")
    bda_id: str = Field(..., description="Reference to the BDA report")
    nomination_id: str = Field(..., description="Reference to the original nomination")
    coa_id: str = Field(..., description="COA ID whose logic should be reviewed")
    predicted_effect: EffectOutcome = Field(..., description="What was expected")
    actual_effect: EffectOutcome = Field(..., description="What actually happened")
    requires_manual_review: bool = Field(default=True, description="Flag for HITL review of Tactical Planner logic")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the flag")

class DriftAlert(BaseModel):
    """Alert triggered when ISR Observer confidence drops below threshold."""
    alert_id: str = Field(..., description="Unique identifier for this drift alert")
    target_classification: TargetClassification = Field(..., description="Target type experiencing confidence degradation")
    current_avg_confidence: float = Field(..., ge=0.0, le=1.0, description="Current rolling average confidence score")
    threshold: float = Field(default=0.80, ge=0.0, le=1.0, description="Minimum acceptable confidence threshold")
    sample_count: int = Field(..., description="Number of detections in the rolling window")
    recommendation: str = Field(default="Generate new training data", description="Recommended remediation action")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the alert")

class FlywheelHealthReport(BaseModel):
    """Weekly report summarising the health of the Process Improvement Flywheel."""
    report_id: str = Field(..., description="Unique identifier for this report")
    reporting_period_start: str = Field(..., description="ISO 8601 start of the reporting period")
    reporting_period_end: str = Field(..., description="ISO 8601 end of the reporting period")
    total_kill_chains_audited: int = Field(..., description="Total number of kill chains reviewed")
    successful_outcomes: int = Field(..., description="Kill chains where effect matched prediction")
    discrepancies_flagged: int = Field(..., description="Number of discrepancy flags raised")
    drift_alerts_triggered: int = Field(..., description="Number of drift alerts triggered")
    avg_decision_speed_seconds: float = Field(..., description="Average time from detection to engagement in seconds")
    decision_speed_delta_pct: float = Field(..., description="Percent change in decision speed vs prior period")
    labor_reduction_pct: float = Field(..., description="Estimated reduction in human eyes-on-glass time as a percentage")
    flags: List[DiscrepancyFlag] = Field(default_factory=list, description="Discrepancy flags from this period")
    drift_alerts: List[DriftAlert] = Field(default_factory=list, description="Drift alerts from this period")


# ──────────────────────────────────────────────────────────────
# Battlespace Management Agent (Gaia Integration) Schemas
# ──────────────────────────────────────────────────────────────

class Coordinate(BaseModel):
    lat: float = Field(..., description="Latitude in decimal degrees")
    lon: float = Field(..., description="Longitude in decimal degrees")
    alt_m: Optional[float] = Field(default=None, description="Altitude in metres above sea level")


class ThreatType(str, Enum):
    SAM_SHORT = "SAM_SHORT_RANGE"
    SAM_MEDIUM = "SAM_MEDIUM_RANGE"
    SAM_LONG = "SAM_LONG_RANGE"
    AAA = "ANTI_AIRCRAFT_ARTILLERY"
    EW = "ELECTRONIC_WARFARE"


class ThreatRing(BaseModel):
    threat_id: str = Field(..., description="Unique identifier for this threat ring")
    center: Coordinate = Field(..., description="Geographic center of the threat envelope")
    range_km: float = Field(..., gt=0, description="Effective engagement radius in kilometres")
    threat_type: ThreatType = Field(..., description="Category of the threat system")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Intel confidence that this threat is active")
    source_track_id: Optional[str] = Field(default=None, description="Link back to the ISR track that identified this threat")


class MapLayerType(str, Enum):
    TERRAIN = "TERRAIN"
    THREATS = "THREATS"
    FRIENDLY_UNITS = "FRIENDLY_UNITS"
    ISR_DETECTIONS = "ISR_DETECTIONS"
    MISSION_PATHS = "MISSION_PATHS"
    THIRD_PARTY = "THIRD_PARTY"


class MapLayer(BaseModel):
    layer_id: str = Field(..., description="Unique identifier for the map layer")
    layer_type: MapLayerType = Field(..., description="Category of data this layer represents")
    name: str = Field(..., description="Human-readable layer name")
    visible: bool = Field(default=True, description="Whether this layer is currently displayed on the COP")
    data_source: Optional[str] = Field(default=None, description="URI or reference to the backing data feed")


class TerrainType(str, Enum):
    FLAT = "FLAT"
    HILLY = "HILLY"
    MOUNTAINOUS = "MOUNTAINOUS"
    URBAN = "URBAN"
    WATER = "WATER"
    FOREST = "FOREST"


class Waypoint(BaseModel):
    sequence: int = Field(..., ge=0, description="Order of this waypoint in the mission path")
    position: Coordinate = Field(..., description="Geographic position of the waypoint")
    terrain: TerrainType = Field(default=TerrainType.FLAT, description="Terrain classification at this waypoint")
    is_safe: bool = Field(default=True, description="True if no known threat ring covers this point")
    notes: Optional[str] = Field(default=None, description="Optional context (e.g., 'crossing river', 'ridge masking')")


class MissionPath(BaseModel):
    path_id: str = Field(..., description="Unique identifier for the generated mission path")
    waypoints: List[Waypoint] = Field(..., description="Ordered sequence of waypoints")
    total_distance_km: float = Field(..., ge=0, description="Total path distance in kilometres")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Aggregate risk score (0 = minimal risk, 1 = extreme)")
    avoided_threats: List[str] = Field(default_factory=list, description="IDs of threat rings this path routes around")


class BattlespaceManagerOutput(BaseModel):
    mission_path: MissionPath = Field(..., description="The terrain-aware mission path generated for the Tactical Planner")
    active_threat_rings: List[ThreatRing] = Field(default_factory=list, description="Currently known threat envelopes in the AO")
    active_layers: List[MapLayer] = Field(default_factory=list, description="Map layers comprising the current COP")


# ── Strategy Analyst schemas ──────────────────────────────────────────────────

class EngagementDecision(str, Enum):
    NOMINATE = "Nominate"       # Forward to the Strike Board
    MONITOR = "Monitor"         # Continue observing, do not engage
    REJECT = "Reject"           # Does not meet ROE criteria

class TargetNomination(BaseModel):
    track_id: str = Field(..., description="Track ID being evaluated")
    decision: EngagementDecision = Field(..., description="Engagement recommendation")
    roe_compliance: bool = Field(..., description="True if engagement complies with current ROE")
    collateral_risk: str = Field(..., description="LOW / MEDIUM / HIGH collateral damage estimate")
    reasoning: str = Field(..., description="Why-trace explaining the decision")

class StrategyAnalystOutput(BaseModel):
    nominations: List[TargetNomination] = Field(..., description="Evaluated targets with engagement recommendations")
    summary: str = Field(..., description="Brief narrative summary of the current threat picture")


# ── Effectors Agent schemas ───────────────────────────────────────────────────

class BDAResult(str, Enum):
    DESTROYED = "Target Destroyed"
    DAMAGED = "Target Damaged"
    MISSED = "Target Missed"
    PENDING = "Assessment Pending"

class BattleDamageAssessment(BaseModel):
    strike_id: str = Field(..., description="Unique identifier for this strike event")
    target_track_id: str = Field(..., description="Track that was engaged")
    coa_id: str = Field(..., description="COA that was executed")
    result: BDAResult = Field(..., description="Outcome of the strike")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the BDA assessment")
    post_strike_imagery: Optional[str] = Field(None, description="URI to post-strike imagery if available")
    notes: str = Field(default="", description="Additional analyst notes")

class EffectorsAgentOutput(BaseModel):
    task_status: str = Field(..., description="Current status: Tasked / In-Flight / Complete")
    bda: Optional[BattleDamageAssessment] = Field(None, description="Battle Damage Assessment, populated post-strike")
    reasoning: str = Field(..., description="Why-trace for effector tasking or BDA conclusion")


# ── AI Tasking Manager schemas ────────────────────────────────────────────────

class SensorStatusEnum(str, Enum):
    AVAILABLE = "Available"
    TASKED = "Tasked"
    OFFLINE = "Offline"
    MAINTENANCE = "Maintenance"


class CollectionType(str, Enum):
    """Type of collection requested from a sensor asset."""
    EO_IR = "EO/IR"           # Electro-Optical / Infrared imaging
    SAR = "SAR"               # Synthetic Aperture Radar
    SIGINT = "SIGINT"         # Signals Intelligence
    FMV = "FMV"               # Full Motion Video
    GMTI = "GMTI"             # Ground Moving Target Indicator


class SensorAsset(BaseModel):
    """Models a single ISR sensor platform available for tasking."""
    asset_id: str = Field(..., description="Unique identifier for this sensor asset")
    asset_name: str = Field(..., description="Human-readable name (e.g., 'MQ-9 Reaper #3', 'WorldView-4')")
    sensor_type: SensorSource = Field(..., description="UAV, Satellite, or SIGINT")
    status: SensorStatusEnum = Field(..., description="Current operational status")
    lat: float = Field(..., description="Current latitude of the asset")
    lon: float = Field(..., description="Current longitude of the asset")
    capabilities: List[CollectionType] = Field(default_factory=list, description="Collection types this asset supports")
    time_to_station_minutes: Optional[float] = Field(None, description="Estimated minutes to reach a given target area")


class SensorTaskingOrder(BaseModel):
    """A directive issued by the AI Tasking Manager to redirect a sensor asset."""
    order_id: str = Field(..., description="Unique identifier for this tasking order")
    asset_id: str = Field(..., description="ID of the sensor asset being tasked")
    target_detection_id: str = Field(..., description="Detection ID that triggered this retasking")
    collection_type: CollectionType = Field(..., description="Type of collection requested")
    priority: int = Field(..., ge=1, le=5, description="Tasking priority 1 (routine) – 5 (immediate)")
    estimated_collection_time_minutes: float = Field(..., description="Expected time until imagery/data is available")
    reasoning: str = Field(..., description="Why this asset was selected for this target")


class TaskingManagerOutput(BaseModel):
    """Structured output of the AI Tasking Manager agent."""
    tasking_orders: List[SensorTaskingOrder] = Field(
        default_factory=list,
        description="Sensor retasking orders issued (empty if confidence is above threshold)"
    )
    confidence_gap: float = Field(
        ..., ge=0.0, le=1.0,
        description="How far below the confidence threshold the triggering detection is"
    )
    reasoning: str = Field(..., description="Why-trace explaining the retasking decision or lack thereof")


# ── Synthesis & Query Agent schemas ───────────────────────────────────────────

class SITREPQuery(BaseModel):
    """Inbound model: a commander's natural-language query plus optional context."""
    query: str = Field(..., description="Free-form natural-language question from the Commanding Officer")
    context_tracks: Optional[List[Track]] = Field(default=None, description="Current ISR tracks to reason over")
    context_nominations: Optional[List[TargetNomination]] = Field(default=None, description="Current Strike Board state")
    context_bda: Optional[List[BattleDamageAssessment]] = Field(default=None, description="Recent BDA results")

class SynthesisQueryOutput(BaseModel):
    """Outbound model: the agent's structured SITREP response."""
    sitrep_narrative: str = Field(..., description="Human-readable situational report for the Commanding Officer")
    key_threats: List[str] = Field(default_factory=list, description="Bulleted list of the most critical current threats")
    recommended_actions: List[str] = Field(default_factory=list, description="Suggested next steps for the CO")
    data_sources_consulted: List[str] = Field(default_factory=list, description="Which data feeds contributed to this SITREP")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in the assessment")


# ── Pattern Analyzer schemas ─────────────────────────────────────────────────

class AnomalyType(str, Enum):
    ROUTE_FREQUENCY_CHANGE = "Route Frequency Change"
    NEW_FACILITY = "New Facility"
    MOVEMENT_SURGE = "Movement Surge"
    PATTERN_BREAK = "Pattern Break"
    COMMS_ANOMALY = "Communications Anomaly"

class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class PatternAnomaly(BaseModel):
    anomaly_id: str = Field(..., description="Unique identifier for this anomaly")
    anomaly_type: AnomalyType = Field(..., description="Category of the detected anomaly")
    sector: str = Field(..., description="Sector where the anomaly was observed (e.g., 'Bravo')")
    description: str = Field(..., description="Human-readable description of the anomaly")
    severity: AlertSeverity = Field(..., description="Severity level of the anomaly")
    baseline_value: float = Field(..., description="Historical baseline value for the metric")
    observed_value: float = Field(..., description="Currently observed value for the metric")
    deviation_pct: float = Field(..., description="Percentage deviation from baseline")
    first_observed: str = Field(..., description="ISO 8601 timestamp when the anomaly was first detected")
    reasoning: str = Field(..., description="Why-trace explaining why this constitutes an anomaly")

class PatternAnalyzerOutput(BaseModel):
    anomalies: List[PatternAnomaly] = Field(..., description="List of detected anomalies in the assessed sector")
    sector_assessed: str = Field(..., description="The sector that was analyzed")
    historical_window_days: int = Field(..., description="Number of days of historical data used for analysis")
    predictive_alerts: List[str] = Field(default_factory=list, description="Forward-looking alerts triggered by pattern deviations")
    summary: str = Field(..., description="Narrative summary of the overall pattern assessment")
