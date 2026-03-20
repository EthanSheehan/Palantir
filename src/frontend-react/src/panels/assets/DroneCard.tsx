import React from 'react';
import { UAV } from '../../store/types';
import { useSimStore } from '../../store/SimulationStore';
import { MODE_STYLES } from '../../shared/constants';
import { DroneCardDetails } from './DroneCardDetails';
import { TransitionToast } from './TransitionToast';

const verbMap: Record<string, string> = {
  FOLLOW: 'FOLLOWING',
  PAINT: 'PAINTING',
  INTERCEPT: 'INTERCEPTING',
};

interface DroneCardProps {
  uav: UAV;
}

export function DroneCard({ uav }: DroneCardProps) {
  const trackedDroneId = useSimStore(s => s.trackedDroneId);
  const setTrackedDrone = useSimStore(s => s.setTrackedDrone);
  const selectDrone = useSimStore(s => s.selectDrone);
  const setDroneCamVisible = useSimStore(s => s.setDroneCamVisible);

  const pendingTransitions = useSimStore(s => s.pendingTransitions);
  const isTracked = uav.id === trackedDroneId;
  const modeStyle = MODE_STYLES[uav.mode] || { color: '#94a3b8', label: uav.mode };
  const pendingTransition = pendingTransitions[uav.id] ?? null;

  const handleClick = () => {
    if (isTracked) {
      setTrackedDrone(null);
      selectDrone(null);
      setDroneCamVisible(false);
    } else {
      setTrackedDrone(uav.id);
      selectDrone(uav.id);
      setDroneCamVisible(true);
    }
  };

  const cardStyle: React.CSSProperties = {
    background: isTracked ? 'rgba(250, 204, 21, 0.15)' : 'rgba(255,255,255,0.04)',
    border: `1px solid ${isTracked ? 'rgba(250, 204, 21, 0.5)' : 'rgba(255,255,255,0.1)'}`,
    borderRadius: 4,
    padding: '8px 10px',
    cursor: 'pointer',
    userSelect: 'none',
  };

  return (
    <div style={cardStyle} onClick={handleClick}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: isTracked ? '#facc15' : '#e2e8f0', fontWeight: 600, fontSize: '0.85rem' }}>
          UAV-{uav.id}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{
            color: modeStyle.color,
            borderColor: modeStyle.color,
            border: '1px solid',
            borderRadius: 3,
            padding: '1px 6px',
            fontSize: '0.65rem',
            fontWeight: 700,
            letterSpacing: '0.05em',
          }}>
            {modeStyle.label}
          </span>
          {uav.mode_source === 'AUTO' && (
            <span style={{
              color: '#f59e0b',
              border: '1px solid rgba(245, 158, 11, 0.5)',
              borderRadius: 3,
              padding: '1px 4px',
              fontSize: '0.6rem',
              fontWeight: 700,
            }}>
              AUTO
            </span>
          )}
        </div>
      </div>

      {uav.tracked_target_id && verbMap[uav.mode] && (
        <div style={{ color: modeStyle.color, fontSize: '0.7rem', marginTop: 4 }}>
          {verbMap[uav.mode]} TGT-{uav.tracked_target_id}
        </div>
      )}

      {uav.tracked_target_ids && uav.tracked_target_ids.length > 0 && (
        <div style={{ fontSize: '0.7rem', marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
          <span style={{ color: '#64748b' }}>TRACKING:</span>
          {uav.tracked_target_ids.map(tid => (
            <span
              key={tid}
              style={{
                cursor: 'pointer',
                color: tid === uav.primary_target_id ? '#facc15' : '#94a3b8',
                fontWeight: tid === uav.primary_target_id ? 700 : 400,
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.textDecoration = 'underline'; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.textDecoration = 'none'; }}
              onClick={(e) => {
                e.stopPropagation();
                useSimStore.getState().selectTarget(tid);
              }}
            >
              TGT-{tid}
              {tid === uav.primary_target_id && uav.tracked_target_ids.length > 1 && (
                <span style={{
                  marginLeft: 3,
                  fontSize: '0.55rem',
                  color: '#facc15',
                  border: '1px solid rgba(250, 204, 21, 0.5)',
                  borderRadius: 2,
                  padding: '0px 3px',
                  fontWeight: 700,
                }}>PRIMARY</span>
              )}
            </span>
          ))}
        </div>
      )}

      {pendingTransition && (
        <TransitionToast uavId={uav.id} pending={pendingTransition} />
      )}

      {isTracked && <DroneCardDetails uav={uav} />}
    </div>
  );
}
