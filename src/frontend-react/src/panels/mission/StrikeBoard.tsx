import React from 'react';
import { useSimStore } from '../../store/SimulationStore';
import { StrikeBoardEntry } from './StrikeBoardEntry';

const STATUS_ORDER: Record<string, number> = {
  PENDING: 0, APPROVED: 1, RETASKED: 2, REJECTED: 3,
};

export function StrikeBoard() {
  const entries = useSimStore(s => s.strikeBoard);
  const sorted = [...entries].sort((a, b) =>
    (STATUS_ORDER[a.status] ?? 4) - (STATUS_ORDER[b.status] ?? 4)
  );

  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, letterSpacing: '0.05em' }}>
        STRIKE BOARD
      </div>
      {sorted.length === 0 ? (
        <div style={{ color: '#94a3b8', fontSize: 12 }}>No active strike packages.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sorted.map(entry => (
            <StrikeBoardEntry key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
