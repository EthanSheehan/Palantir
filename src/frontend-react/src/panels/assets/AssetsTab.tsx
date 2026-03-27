import React from 'react';
import { useSimStore } from '../../store/SimulationStore';
import { DroneCard } from './DroneCard';
import { OpsAlertsPanel } from './OpsAlertsPanel';

export function AssetsTab() {
  const uavs = useSimStore(s => s.uavs);

  if (uavs.length === 0) {
    return <div style={{ padding: 16, color: '#94a3b8' }}>No UAVs Active.</div>;
  }

  return (
    <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 8, overflow: 'auto', flex: 1 }}>
      <OpsAlertsPanel />
      {uavs.map(uav => (
        <DroneCard key={uav.id} uav={uav} />
      ))}
    </div>
  );
}
