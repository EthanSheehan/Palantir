import React, { useMemo } from 'react';
import { useSimStore } from '../store/SimulationStore';

interface Phase {
  key: string;
  label: string;
  states: string[];
}

const PHASES: Phase[] = [
  { key: 'FIND',    label: 'FIND',    states: ['DETECTED'] },
  { key: 'FIX',     label: 'FIX',     states: ['CLASSIFIED'] },
  { key: 'TRACK',   label: 'TRACK',   states: ['VERIFIED'] },
  { key: 'TARGET',  label: 'TARGET',  states: ['NOMINATED'] },
  { key: 'ENGAGE',  label: 'ENGAGE',  states: ['ENGAGED', 'ENGAGING'] },
  { key: 'ASSESS',  label: 'ASSESS',  states: ['ASSESSED', 'BDA'] },
];

function phaseColor(count: number): string {
  if (count === 0) return '#334155';
  if (count <= 2) return '#16a34a';
  if (count <= 5) return '#ca8a04';
  return '#dc2626';
}

export function KillChainRibbon() {
  const targets = useSimStore(s => s.targets);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const phase of PHASES) {
      result[phase.key] = targets.filter(t =>
        phase.states.some(s => t.state?.toUpperCase().includes(s))
      ).length;
    }
    return result;
  }, [targets]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'stretch',
        height: 28,
        background: 'rgba(15, 20, 30, 0.92)',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        flexShrink: 0,
        fontFamily: 'monospace',
        letterSpacing: '0.06em',
        overflow: 'hidden',
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        padding: '0 10px',
        color: '#475569',
        fontSize: 9,
        fontWeight: 700,
        textTransform: 'uppercase',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0,
      }}>
        F2T2EA
      </div>
      {PHASES.map((phase, i) => {
        const count = counts[phase.key] ?? 0;
        const color = phaseColor(count);
        const isLast = i === PHASES.length - 1;
        return (
          <div
            key={phase.key}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              borderRight: isLast ? 'none' : '1px solid rgba(255,255,255,0.06)',
              background: count > 0 ? `${color}18` : 'transparent',
              transition: 'background 0.3s',
              minWidth: 0,
              cursor: 'default',
            }}
          >
            <span style={{
              fontSize: 8,
              color: count > 0 ? color : '#475569',
              fontWeight: 700,
              textTransform: 'uppercase',
              lineHeight: 1,
            }}>
              {phase.label}
            </span>
            <span style={{
              fontSize: 11,
              color: count > 0 ? color : '#334155',
              fontWeight: 700,
              lineHeight: 1,
              marginTop: 2,
            }}>
              {count}
            </span>
          </div>
        );
      })}
    </div>
  );
}
