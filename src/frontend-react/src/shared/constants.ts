export const MODE_STYLES: Record<string, { color: string; label: string }> = {
  IDLE:          { color: '#3b82f6', label: 'IDLE' },
  SEARCH:        { color: '#22c55e', label: 'SEARCH' },
  FOLLOW:        { color: '#a78bfa', label: 'FOLLOW' },
  PAINT:         { color: '#ef4444', label: 'PAINT' },
  INTERCEPT:     { color: '#ff6400', label: 'INTERCEPT' },
  REPOSITIONING: { color: '#eab308', label: 'TRANSIT' },
  RTB:           { color: '#64748b', label: 'RTB' },
};

export const TARGET_MAP: Record<string, { color: string; label: string }> = {
  SAM:       { color: '#ff4444', label: 'SAM' },
  TEL:       { color: '#ffa500', label: 'TEL' },
  TRUCK:     { color: '#eab308', label: 'TRK' },
  CP:        { color: '#a855f7', label: 'CP' },
  MANPADS:   { color: '#ec4899', label: 'MAN' },
  RADAR:     { color: '#06b6d4', label: 'RDR' },
  ARTILLERY: { color: '#92400e', label: 'ART' },
  APC:       { color: '#94a3b8', label: 'APC' },
  C2_NODE:   { color: '#06b6d4', label: 'C2' },
  LOGISTICS: { color: '#94a3b8', label: 'LOG' },
};

export const STATE_COLORS: Record<string, { color: string; bg: string }> = {
  DETECTED:    { color: '#eab308', bg: 'rgba(234, 179, 8, 0.15)' },
  IDENTIFIED:  { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
  TRACKED:     { color: '#f97316', bg: 'rgba(249, 115, 22, 0.15)' },
  NOMINATED:   { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
  ENGAGED:     { color: '#dc2626', bg: 'rgba(220, 38, 38, 0.25)' },
  NEUTRALIZED: { color: '#64748b', bg: 'rgba(100, 116, 139, 0.15)' },
};

export const TARGET_STYLES: Record<string, { color: string; shape: string }> = {
  SAM:       { color: '#ff0000', shape: 'diamond' },
  TEL:       { color: '#ff8c00', shape: 'triangle' },
  TRUCK:     { color: '#ffffff', shape: 'rect' },
  CP:        { color: '#ff6400', shape: 'square' },
  MANPADS:   { color: '#c800c8', shape: 'circle' },
  RADAR:     { color: '#00ffff', shape: 'hexagon' },
  C2_NODE:   { color: '#ffff00', shape: 'diamond' },
  LOGISTICS: { color: '#b4b4b4', shape: 'rect' },
  ARTILLERY: { color: '#ff4444', shape: 'triangle' },
  APC:       { color: '#88cc88', shape: 'square' },
};

export const SEVERITY_STYLES: Record<string, { color: string; border: string }> = {
  INFO:     { color: '#06b6d4', border: '#06b6d4' },
  WARNING:  { color: '#f59e0b', border: '#f59e0b' },
  CRITICAL: { color: '#ef4444', border: '#ef4444' },
};

export const SENSOR_RANGE_KM = 15;
export const HFOV_DEG = 60;
export const EARTH_R = 6378137;
export const THREAT_RING_RADIUS = 5000;
export const THREAT_RING_TYPES = new Set(['SAM', 'MANPADS']);
export const MAX_ASSISTANT_MESSAGES = 50;
