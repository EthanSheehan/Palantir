import React from 'react';
import { CoverageGap } from '../../store/types';

interface CoverageGapAlertProps {
  gaps: CoverageGap[];
}

export function CoverageGapAlert({ gaps }: CoverageGapAlertProps) {
  if (gaps.length === 0) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.7rem', fontStyle: 'italic' }}>
        Full coverage — no gaps detected.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {gaps.map(gap => (
        <div
          key={`${gap.zone_x}-${gap.zone_y}`}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <span style={{ color: '#f59e0b', fontSize: '0.75rem', lineHeight: 1 }}>
            &#9888;
          </span>
          <span style={{ color: '#f59e0b', fontSize: '0.7rem' }}>
            Zone ({gap.zone_x},{gap.zone_y}) — no UAV coverage
          </span>
        </div>
      ))}
    </div>
  );
}
