import React from 'react';
import { Button, Intent } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';
import { useSendMessage } from '../../App';

const GRID_LABELS: Record<number, { text: string; color: string; border: string }> = {
  0: { text: 'Grid Visibility: OFF', color: '#e2e8f0', border: 'rgba(148,163,184,0.2)' },
  1: { text: 'Grid Visibility: SQUARES ONLY', color: '#a78bfa', border: 'rgba(167,139,250,0.5)' },
  2: { text: 'Grid Visibility: ON', color: '#38bdf8', border: 'rgba(56,189,248,0.5)' },
};

export function GridControls() {
  const gridVisState = useSimStore(s => s.gridVisState);
  const cycleGridVis = useSimStore(s => s.cycleGridVis);
  const showAllWaypoints = useSimStore(s => s.showAllWaypoints);
  const toggleAllWaypoints = useSimStore(s => s.toggleAllWaypoints);
  const sendMessage = useSendMessage();

  const gridStyle = GRID_LABELS[gridVisState] || GRID_LABELS[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <button
        onClick={cycleGridVis}
        style={{
          background: 'transparent',
          border: `1px solid ${gridStyle.border}`,
          color: gridStyle.color,
          padding: '6px 12px',
          borderRadius: 4,
          cursor: 'pointer',
          fontSize: 12,
        }}
      >
        {gridStyle.text}
      </button>
      <button
        onClick={toggleAllWaypoints}
        style={{
          background: 'transparent',
          border: `1px solid ${showAllWaypoints ? 'rgba(56,189,248,0.5)' : 'rgba(148,163,184,0.2)'}`,
          color: showAllWaypoints ? '#38bdf8' : '#e2e8f0',
          padding: '6px 12px',
          borderRadius: 4,
          cursor: 'pointer',
          fontSize: 12,
        }}
      >
        All Waypoints: {showAllWaypoints ? 'ON' : 'OFF'}
      </button>
      <Button
        intent={Intent.WARNING}
        minimal
        small
        text="Override: Reset Grid"
        onClick={() => sendMessage({ action: 'reset' })}
      />
    </div>
  );
}
