import React, { useEffect, useState } from 'react';
import { useSimStore } from '../store/SimulationStore';

export function DemoBanner() {
  const demoMode = useSimStore((s) => s.demoMode);
  const [pulse, setPulse] = useState(true);

  useEffect(() => {
    if (!demoMode) return;
    const id = setInterval(() => setPulse((p) => !p), 800);
    return () => clearInterval(id);
  }, [demoMode]);

  if (!demoMode) return null;

  return (
    <div
      style={{
        width: '100%',
        height: 32,
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        background: 'linear-gradient(90deg, rgba(239,68,68,0.18) 0%, rgba(20,20,20,0.95) 60%)',
        borderBottom: '1px solid rgba(239, 68, 68, 0.35)',
        flexShrink: 0,
        overflow: 'hidden',
        fontFamily: 'monospace',
        letterSpacing: '0.06em',
      }}
    >
      {/* Red accent stripe */}
      <div style={{ width: 3, height: '100%', background: '#ef4444', flexShrink: 0 }} />

      {/* Pulse dot */}
      <div style={{ padding: '0 10px', display: 'flex', alignItems: 'center' }}>
        <div
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: pulse ? '#ef4444' : 'rgba(239,68,68,0.25)',
            boxShadow: pulse ? '0 0 6px 2px rgba(239,68,68,0.6)' : 'none',
            transition: 'background 0.2s, box-shadow 0.2s',
            flexShrink: 0,
          }}
        />
      </div>

      {/* Main label */}
      <span style={{ color: '#ef4444', fontSize: 11, fontWeight: 700, textTransform: 'uppercase' }}>
        DEMO
      </span>

      <div style={{ width: 1, height: 16, background: 'rgba(239,68,68,0.3)', margin: '0 10px' }} />

      {/* Mode description */}
      <span style={{ color: '#94a3b8', fontSize: 10, textTransform: 'uppercase' }}>
        F2T2EA Kill Chain
      </span>

      <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.08)', margin: '0 10px' }} />

      <span style={{ color: '#64748b', fontSize: 10, textTransform: 'uppercase' }}>
        Auto-pilot Active
      </span>

      {/* Right-side badge */}
      <div style={{ marginLeft: 'auto', marginRight: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            background: 'rgba(239,68,68,0.12)',
            border: '1px solid rgba(239,68,68,0.4)',
            color: '#ef4444',
            fontSize: 9,
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: 2,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
          }}
        >
          SIM
        </span>
      </div>
    </div>
  );
}
