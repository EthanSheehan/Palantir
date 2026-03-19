import React from 'react';
import { Target } from '../../store/types';

interface ThreatSummaryProps {
  visibleTargets: Target[];
}

export function ThreatSummary({ visibleTargets }: ThreatSummaryProps) {
  const neutralized = visibleTargets.filter(t => (t.state || '') === 'NEUTRALIZED').length;
  const active = visibleTargets.length - neutralized;

  return (
    <div style={{
      padding: '6px 10px',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      fontSize: '0.75rem',
      color: '#64748b',
    }}>
      <span style={{ color: '#ef4444', fontWeight: 700 }}>{active} Active</span>
      {' / '}
      <span style={{ color: '#64748b' }}>{neutralized} Neutralized</span>
    </div>
  );
}
