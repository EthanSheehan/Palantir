import React, { useEffect, useState } from 'react';
import { Button, ButtonGroup, Intent } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import type { MapMode } from '../store/types';

const MODES: { key: MapMode; label: string; shortcut: string }[] = [
  { key: 'OPERATIONAL', label: 'OPS', shortcut: '1' },
  { key: 'COVERAGE', label: 'COV', shortcut: '2' },
  { key: 'THREAT', label: 'THR', shortcut: '3' },
  { key: 'FUSION', label: 'FUS', shortcut: '4' },
  { key: 'SWARM', label: 'SWM', shortcut: '5' },
  { key: 'TERRAIN', label: 'TRN', shortcut: '6' },
];

export function MapModeBar() {
  const mapMode = useSimStore((s) => s.mapMode);
  const setMapMode = useSimStore((s) => s.setMapMode);
  const [satLensActive, setSatLensActive] = useState(false);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const modeMap: Record<string, MapMode> = {
        '1': 'OPERATIONAL', '2': 'COVERAGE', '3': 'THREAT',
        '4': 'FUSION', '5': 'SWARM', '6': 'TERRAIN',
      };
      const mode = modeMap[e.key];
      if (mode) setMapMode(mode);
      if (e.key === 's' || e.key === 'S') setSatLensActive((v) => !v);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [setMapMode]);

  return (
    <div style={{
      position: 'absolute',
      top: 16,
      right: 16,
      zIndex: 10,
      background: 'rgba(0,0,0,0.7)',
      borderRadius: 4,
      padding: 4,
      border: '1px solid rgba(255,255,255,0.15)',
      display: 'flex',
      alignItems: 'center',
    }}>
      <ButtonGroup>
        {MODES.map((m) => (
          <Button
            key={m.key}
            small
            active={mapMode === m.key}
            intent={mapMode === m.key ? Intent.PRIMARY : Intent.NONE}
            onClick={() => setMapMode(m.key)}
            title={`${m.label} (${m.shortcut})`}
          >
            {m.shortcut}: {m.label}
          </Button>
        ))}
      </ButtonGroup>
      <Button
        small
        active={satLensActive}
        intent={satLensActive ? Intent.SUCCESS : Intent.NONE}
        onClick={() => {
          window.dispatchEvent(new CustomEvent('grid-sentinel:toggleSatLens'));
          setSatLensActive((v) => !v);
        }}
        title="Satellite Lens (S)"
        style={{ marginLeft: 8 }}
      >
        SAT
      </Button>
    </div>
  );
}
