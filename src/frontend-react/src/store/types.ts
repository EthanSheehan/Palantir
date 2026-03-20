export interface SensorContributionPayload {
  uav_id: number;
  sensor_type: 'EO_IR' | 'SAR' | 'SIGINT';
  confidence: number;
}

export interface UAV {
  id: number;
  lat: number;
  lon: number;
  altitude_m: number;
  mode: 'IDLE' | 'SEARCH' | 'FOLLOW' | 'PAINT' | 'INTERCEPT' | 'REPOSITIONING' | 'RTB' | 'SUPPORT' | 'VERIFY' | 'OVERWATCH' | 'BDA';
  heading_deg: number;
  tracked_target_id: number | null;
  tracked_target_ids: number[];
  primary_target_id: number | null;
  sensor_type: string;
  sensors: string[];
  fuel_hours: number;
  autonomy_override: 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS' | null;
  mode_source: 'HUMAN' | 'AUTO';
  pending_transition: { mode: string; reason: string; expires_at: number } | null;
}

export interface Target {
  id: number;
  lat: number;
  lon: number;
  type: string;
  state: string;
  detected: boolean;
  detection_confidence: number;
  concealed?: boolean;
  fused_confidence: number;
  sensor_count: number;
  tracked_by_uav_id: number | null;
  tracked_by_uav_ids: number[];
  sensor_contributions: SensorContributionPayload[];
  detected_by_sensor: string | null;
  is_emitting: boolean;
  heading_deg: number;
  threat_range_km: number | null;
  detection_range_km: number | null;
  time_in_state_sec: number;
  next_threshold: number | null;
}

export interface EnemyUAV {
  id: number;
  lat: number;
  lon: number;
  mode: 'RECON' | 'ATTACK' | 'JAMMING' | 'EVADING' | 'DESTROYED';
  behavior: string;
  heading_deg: number;
  detected: boolean;
  fused_confidence: number;
  sensor_count: number;
  is_jamming: boolean;
}

export interface Zone {
  x_idx: number;
  y_idx: number;
  lat: number;
  lon: number;
  width: number;
  height: number;
  imbalance: number;
}

export interface FlowLine {
  source: [number, number];
  target: [number, number];
}

export interface SwarmTask {
  target_id: number;
  assigned_uav_ids: number[];
  sensor_coverage: string[];
  formation_type: string;
}

export interface StrikeEntry {
  id: string;
  target_type: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'RETASKED';
  detection_confidence: number;
  priority_score: number;
  roe_evaluation: string;
}

export interface COA {
  id: string;
  effector_name: string;
  effector_type: string;
  pk_estimate: number;
  time_to_effect_min: number;
  risk_score: number;
  composite_score: number;
  status: string;
}

export interface TheaterBounds {
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
}

export interface TheaterInfo {
  name: string;
  bounds: TheaterBounds;
}

export interface AssistantMessage {
  timestamp: string;
  text: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
}

export interface HitlUpdate {
  text: string;
  severity: string;
  coas?: COA[];
  entry_id?: string;
}

export interface SimStatePayload {
  uavs: UAV[];
  targets: Target[];
  zones: Zone[];
  flows: FlowLine[];
  strike_board: StrikeEntry[];
  theater: TheaterInfo | null;
  demo_mode: boolean;
  autonomy_level: 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS';
  sitrep_response?: string;
  hitl_update?: HitlUpdate | string;
  enemy_uavs?: EnemyUAV[];
  swarm_tasks?: SwarmTask[];
}
