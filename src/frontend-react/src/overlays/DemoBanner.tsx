import React from 'react';
import { useSimStore } from '../store/SimulationStore';

export function DemoBanner() {
  const demoMode = useSimStore((s) => s.demoMode);

  if (!demoMode) return null;

  return (
    <div
      style={{
        width: '100%',
        height: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(239, 68, 68, 0.15)',
        borderBottom: '1px solid rgba(239, 68, 68, 0.4)',
        color: '#ef4444',
        fontFamily: 'monospace',
        fontSize: 12,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        flexShrink: 0,
      }}
    >
      DEMO MODE — F2T2EA KILL CHAIN AUTO-PILOT ACTIVE
    </div>
  );
}
