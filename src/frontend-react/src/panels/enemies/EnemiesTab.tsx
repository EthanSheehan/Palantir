import { useRef } from 'react';
import { useSimStore } from '../../store/SimulationStore';
import { ThreatSummary } from './ThreatSummary';
import { EnemyCard } from './EnemyCard';
import { EnemyUAVCard } from './EnemyUAVCard';

export function EnemiesTab() {
  const targets = useSimStore(s => s.targets);
  const uavs = useSimStore(s => s.uavs);
  const enemyUavs = useSimStore(s => s.enemyUavs);

  // Track which target IDs have been seen — once visible, keep showing
  // (prevents flicker when confidence briefly dips below threshold)
  const seenIdsRef = useRef<Set<number>>(new Set());

  const visibleTargets = targets.filter(t => {
    const targetState = t.state || (t.detected ? 'DETECTED' : 'UNDETECTED');
    if (targetState !== 'UNDETECTED') {
      seenIdsRef.current.add(t.id);
      return true;
    }
    // Keep showing if previously seen and confidence > 0
    if (seenIdsRef.current.has(t.id) && t.detection_confidence > 0) {
      return true;
    }
    if (t.detection_confidence === 0) {
      seenIdsRef.current.delete(t.id);
    }
    return false;
  });

  // Stable sort: by ID so cards don't jump around
  visibleTargets.sort((a, b) => a.id - b.id);

  const detectedEnemyUavs = enemyUavs.filter(e => e.detected);

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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <ThreatSummary visibleTargets={visibleTargets} />
      {visibleTargets.length === 0 && detectedEnemyUavs.length === 0 ? (
        <div style={{ padding: 16, color: '#94a3b8' }}>No hostile entities detected.</div>
      ) : (
        <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 6, overflow: 'auto', flex: 1 }}>
          {visibleTargets.map(t => (
            <EnemyCard key={t.id} target={t} trackers={trackingMap[t.id] || []} />
          ))}
          {detectedEnemyUavs.length > 0 && (
            <>
              <div style={{ padding: '8px 0 4px', color: '#ef4444', fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>
                Airborne Threats ({detectedEnemyUavs.length})
              </div>
              {detectedEnemyUavs.map(e => (
                <EnemyUAVCard key={e.id} enemyUav={e} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
