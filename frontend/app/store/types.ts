/** Domain entity types matching backend Pydantic models */

export interface Position {
  lon: number;
  lat: number;
  alt_m?: number;
}

export interface Velocity {
  vx: number;
  vy: number;
  vz?: number;
}

export interface Asset {
  id: string;
  name?: string;
  type?: string;
  position: Position;
  velocity?: Velocity;
  heading_deg?: number;
  battery_pct?: number;
  link_quality?: number;
  status: string;
  mode?: string;
  health?: string;
  mission_id?: string;
  capabilities?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface Mission {
  id: string;
  name: string;
  type: string;
  priority: string;
  state: string;
  objective?: string;
  constraints?: Record<string, unknown>;
  asset_ids?: string[];
  task_ids?: string[];
  tags?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface Task {
  id: string;
  mission_id: string;
  type: string;
  target?: Record<string, unknown>;
  state: string;
  dependencies?: string[];
  constraints?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface Command {
  id: string;
  type: string;
  target_type: string;
  target_id: string;
  payload?: Record<string, unknown>;
  state: string;
  created_at?: string;
  validated_at?: string;
  sent_at?: string;
  completed_at?: string;
}

export interface TimelineReservation {
  id: string;
  asset_id: string;
  phase: string;
  start_time: string;
  end_time: string;
  status: string;
  source?: string;
}

export interface Alert {
  id: string;
  type: string;
  severity: string;
  state: string;
  message: string;
  source_type?: string;
  source_id?: string;
  created_at?: string;
  acknowledged_at?: string;
}

export interface Recommendation {
  id: string;
  source_zone?: string;
  target_zone?: string;
  confidence?: number;
  suggested_count?: number;
  pressure_delta?: number;
  ttl?: number;
  created_at?: string;
}

export interface LayoutState {
  leftWidth: number;
  leftCollapsed: boolean;
  rightWidth: number;
  rightVisible: boolean;
  timelineExpanded: boolean;
  timelineHeight: number;
}
