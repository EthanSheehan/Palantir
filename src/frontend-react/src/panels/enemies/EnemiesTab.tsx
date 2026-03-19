import React from 'react';
import { useSimStore } from '../../store/SimulationStore';
import { ThreatSummary } from './ThreatSummary';
import { EnemyCard } from './EnemyCard';

export function EnemiesTab() {
  const targets = useSimStore(s => s.targets);
  const uavs = useSimStore(s => s.uavs);

  const visibleTargets = targets.filter(t => {
    const targetState = t.state || (t.detected ? 'DETECTED' : 'UNDETECTED');
    return targetState !== 'UNDETECTED';
  });

  // Build target → UAV tracking map
  const trackingMap: Record<number, Array<{ id: number; mode: string }>> = {};
  uavs.forEach(u => {
    if (u.tracked_target_id !== null && u.tracked_target_id !== undefined) {
      if (!trackingMap[u.tracked_target_id]) {
        trackingMap[u.tracked_target_id] = [];
      }
      trackingMap[u.tracked_target_id].push({ id: u.id, mode: u.mode });
    }
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <ThreatSummary visibleTargets={visibleTargets} />
      {visibleTargets.length === 0 ? (
        <div style={{ padding: 16, color: '#94a3b8' }}>No hostile entities detected.</div>
      ) : (
        <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {visibleTargets.map(t => (
            <EnemyCard key={t.id} target={t} trackers={trackingMap[t.id] || []} />
          ))}
        </div>
      )}
    </div>
  );
}
