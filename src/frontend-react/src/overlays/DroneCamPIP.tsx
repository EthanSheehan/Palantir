import React, { useRef } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { useDroneCam } from '../hooks/useDroneCam';

const STATE_COLORS: Record<string, string> = {
  DETECTED: '#eab308',
  CLASSIFIED: '#f59e0b',
  VERIFIED: '#22c55e',
  NOMINATED: '#ef4444',
};

export function DroneCamPIP() {
  const selectedDroneId = useSimStore((s) => s.selectedDroneId);
  const droneCamVisible = useSimStore((s) => s.droneCamVisible);
  const setDroneCamVisible = useSimStore((s) => s.setDroneCamVisible);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useDroneCam(canvasRef);

  const trackedDroneId = useSimStore((s) => s.trackedDroneId);
  const droneId = trackedDroneId ?? selectedDroneId;
  const drone = useSimStore((s) => s.uavs.find((u) => u.id === droneId));
  const primaryTargetId = drone?.primary_target_id ?? null;
  const target = useSimStore((s) =>
    primaryTargetId !== null ? s.targets.find((t) => t.id === primaryTargetId) ?? null : null
  );

  const isVisible = selectedDroneId !== null && droneCamVisible;

  const showOverlay = target !== null && target !== undefined && target.state !== 'UNDETECTED';
  const stateColor = target ? (STATE_COLORS[target.state] ?? '#00ff00') : '#00ff00';

  return (
    <div
      style={{
        display: isVisible ? 'block' : 'none',
        position: 'absolute',
        bottom: 16,
        right: 16,
        zIndex: 20,
        background: 'rgba(0, 0, 0, 0.85)',
        border: '1px solid rgba(0, 255, 0, 0.4)',
        borderRadius: 4,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 8px',
          borderBottom: '1px solid rgba(0, 255, 0, 0.2)',
        }}
      >
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#00ff00', letterSpacing: '0.1em' }}>
          DRONE CAM
        </span>
        <button
          onClick={() => setDroneCamVisible(false)}
          style={{
            background: 'none',
            border: 'none',
            color: '#666',
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: 1,
            padding: '0 2px',
          }}
        >
          ×
        </button>
      </div>
      <div style={{ position: 'relative' }}>
        <canvas
          ref={canvasRef}
          width={400}
          height={300}
          style={{ display: 'block' }}
        />
        {showOverlay && target && (
          <div
            style={{
              position: 'absolute',
              bottom: 8,
              left: 16,
              pointerEvents: 'none' as const,
              background: 'rgba(0, 0, 0, 0.6)',
              padding: '4px 8px',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#00ff00' }}>
              {(target.fused_confidence * 100).toFixed(0)}% FUSED
            </span>
            <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#00ff00' }}>
              {target.sensor_count} SENSOR{target.sensor_count !== 1 ? 'S' : ''}
            </span>
            <span style={{ fontFamily: 'monospace', fontSize: 11, color: stateColor }}>
              {target.state}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
