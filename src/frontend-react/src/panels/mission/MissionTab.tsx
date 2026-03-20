import React from 'react';
import { Tag, Intent } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';
import { TheaterSelector } from './TheaterSelector';
import { AssistantWidget } from './AssistantWidget';
import { StrikeBoard } from './StrikeBoard';
import { GridControls } from './GridControls';
import { AutonomyToggle } from './AutonomyToggle';

export function MissionTab() {
  const connected = useSimStore(s => s.connected);
  const uavCount = useSimStore(s => s.uavs.length);
  const zoneCount = useSimStore(s => s.zones.length);

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12 }}>
        <Tag intent={connected ? Intent.SUCCESS : Intent.DANGER} minimal>
          {connected ? 'Online' : 'Offline'}
        </Tag>
        <span style={{ color: '#94a3b8' }}>UAVs: {uavCount}</span>
        <span style={{ color: '#94a3b8' }}>Zones: {zoneCount}</span>
      </div>
      <div style={{ marginBottom: 0 }}>
        <AutonomyToggle />
      </div>
      <TheaterSelector />
      <AssistantWidget />
      <StrikeBoard />
      <GridControls />
    </div>
  );
}
