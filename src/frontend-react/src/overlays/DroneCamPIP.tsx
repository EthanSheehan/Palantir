import React, { useRef } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { useDroneCam } from '../hooks/useDroneCam';

export function DroneCamPIP() {
  const selectedDroneId = useSimStore((s) => s.selectedDroneId);
  const droneCamVisible = useSimStore((s) => s.droneCamVisible);
  const setDroneCamVisible = useSimStore((s) => s.setDroneCamVisible);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useDroneCam(canvasRef);

  const isVisible = selectedDroneId !== null && droneCamVisible;

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
      <canvas
        ref={canvasRef}
        width={400}
        height={300}
        style={{ display: 'block' }}
      />
    </div>
  );
}
