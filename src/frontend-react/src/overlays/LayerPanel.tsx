import React from 'react';
import { Checkbox } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';

const LAYERS = [
  { key: 'drones', label: 'Drones' },
  { key: 'targets', label: 'Targets' },
  { key: 'zones', label: 'Zones' },
  { key: 'flows', label: 'Flow Lines' },
  { key: 'coverage', label: 'Coverage' },
  { key: 'threat', label: 'Threat' },
  { key: 'fusion', label: 'Fusion' },
  { key: 'swarm', label: 'Swarm' },
  { key: 'terrain', label: 'Terrain' },
];

export function LayerPanel() {
  const layerVisibility = useSimStore((s) => s.layerVisibility);
  const toggleLayer = useSimStore((s) => s.toggleLayer);

  return (
    <div style={{
      position: 'absolute',
      top: 56,
      right: 16,
      zIndex: 10,
      background: 'rgba(0,0,0,0.7)',
      borderRadius: 4,
      padding: '8px 12px',
      border: '1px solid rgba(255,255,255,0.15)',
      maxHeight: 300,
      overflowY: 'auto' as const,
    }}>
      <div style={{
        fontSize: 11,
        color: '#94a3b8',
        fontFamily: 'monospace',
        marginBottom: 4,
        letterSpacing: 1,
      }}>
        LAYERS
      </div>
      {LAYERS.map((layer) => (
        <Checkbox
          key={layer.key}
          checked={layerVisibility[layer.key] ?? false}
          onChange={() => toggleLayer(layer.key)}
          label={layer.label}
          style={{ marginBottom: 2, fontSize: 12, color: '#e2e8f0' }}
        />
      ))}
    </div>
  );
}
