import React from 'react';
import { ProgressBar, Intent } from '@blueprintjs/core';
import type { UAV, Target } from '../store/types';
import type { SensorMode } from '../store/types';
import { haversineDist } from '../shared/geo';

interface SensorHUDProps {
  drone: UAV | null;
  targets: Target[];
  sensorMode: SensorMode;
}

const SENSOR_MODE_COLORS: Record<SensorMode, string> = {
  EO_IR: '#4A90E2',
  SAR: '#7ED321',
  SIGINT: '#F5A623',
  FUSION: '#00ffff',
};

const COMPASS_LABELS: { deg: number; label: string }[] = [
  { deg: 0, label: 'N' },
  { deg: 45, label: 'NE' },
  { deg: 90, label: 'E' },
  { deg: 135, label: 'SE' },
  { deg: 180, label: 'S' },
  { deg: 225, label: 'SW' },
  { deg: 270, label: 'W' },
  { deg: 315, label: 'NW' },
];

function fuelIntent(fuelHours: number): Intent {
  if (fuelHours > 12) return Intent.SUCCESS;
  if (fuelHours > 5) return Intent.WARNING;
  return Intent.DANGER;
}

function hasThreat(drone: UAV, targets: Target[]): boolean {
  for (const t of targets) {
    if (!drone.fov_targets.includes(t.id)) continue;
    if (t.threat_range_km == null) continue;
    const distM = haversineDist(drone.lat, drone.lon, t.lat, t.lon);
    if (distM / 1000 < t.threat_range_km) return true;
  }
  return false;
}

export function SensorHUD({ drone, targets, sensorMode }: SensorHUDProps) {
  if (!drone) return null;

  const heading = drone.heading_deg ?? 0;
  const threat = hasThreat(drone, targets);

  const compassOffset = -(heading / 360) * 360 - 100;

  const ticks: React.ReactNode[] = [];
  for (let d = -360; d <= 720; d += 10) {
    const pos = ((d + 360 * 2) / 10);
    const isMajor = d % 30 === 0;
    const normalizedDeg = ((d % 360) + 360) % 360;
    const labelEntry = COMPASS_LABELS.find(cl => cl.deg === normalizedDeg);

    ticks.push(
      <div
        key={`${d}-${pos}`}
        style={{
          position: 'absolute',
          left: pos * 10,
          top: 0,
          width: 1,
          height: isMajor ? 14 : 8,
          background: '#00ff0040',
          display: 'inline-block',
        }}
      >
        {labelEntry && (
          <span
            style={{
              position: 'absolute',
              top: 14,
              left: -8,
              fontSize: 9,
              fontFamily: 'monospace',
              color: '#00ff00',
              whiteSpace: 'nowrap',
            }}
          >
            {labelEntry.label}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
      }}
    >
      {/* Keyframes for threat pulse */}
      <style>{`
        @keyframes threatPulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
      `}</style>

      {/* Compass tape — top center */}
      <div
        style={{
          position: 'absolute',
          top: 4,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 200,
          height: 24,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'relative',
            width: 1080,
            height: 24,
            transform: `translateX(${compassOffset}px)`,
          }}
        >
          {ticks}
        </div>
        {/* Center heading indicator */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '4px solid transparent',
            borderRight: '4px solid transparent',
            borderBottom: '6px solid #00ff00',
          }}
        />
      </div>

      {/* Fuel gauge — bottom left */}
      <div
        style={{
          position: 'absolute',
          bottom: 24,
          left: 8,
          width: 80,
        }}
      >
        <div
          style={{ fontSize: 9, fontFamily: 'monospace', color: '#00ff00', marginBottom: 2 }}
        >
          FUEL
        </div>
        <div style={{ height: 6, overflow: 'hidden' }}>
          <ProgressBar
            value={Math.min(drone.fuel_hours / 24, 1)}
            animate={false}
            stripes={false}
            intent={fuelIntent(drone.fuel_hours)}
          />
        </div>
        <div
          style={{ fontSize: 9, fontFamily: 'monospace', color: '#00ff00', marginTop: 2 }}
        >
          {Math.round((drone.fuel_hours / 24) * 100)}%
        </div>
      </div>

      {/* Sensor status — top right */}
      <div
        style={{
          position: 'absolute',
          top: 4,
          right: 8,
          textAlign: 'right',
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontFamily: 'monospace',
            color: SENSOR_MODE_COLORS[sensorMode],
            fontWeight: 'bold',
          }}
        >
          {sensorMode}
        </div>
        <div style={{ fontSize: 9, fontFamily: 'monospace', color: '#00ff00' }}>
          Q: {(drone.sensor_quality * 100).toFixed(0)}%
        </div>
        <div style={{ fontSize: 9, fontFamily: 'monospace', color: '#00ff00' }}>
          TGT: {drone.fov_targets.length}
        </div>
      </div>

      {/* Threat warning — conditional center overlay */}
      {threat && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(255, 0, 0, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            animation: 'threatPulse 1s infinite',
          }}
        >
          <span
            style={{
              font: 'bold 24px monospace',
              color: '#ff0000',
            }}
          >
            THREAT
          </span>
        </div>
      )}
    </div>
  );
}
