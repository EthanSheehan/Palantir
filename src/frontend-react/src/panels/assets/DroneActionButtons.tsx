import React from 'react';
import { UAV } from '../../store/types';
import { useSimStore } from '../../store/SimulationStore';

interface DroneActionButtonsProps {
  uav: UAV;
}

export function DroneActionButtons({ uav }: DroneActionButtonsProps) {
  const isSettingWaypoint = useSimStore(s => s.isSettingWaypoint);
  const setIsSettingWaypoint = useSimStore(s => s.setIsSettingWaypoint);
  const rangeRingDroneIds = useSimStore(s => s.rangeRingDroneIds);
  const toggleRangeRing = useSimStore(s => s.toggleRangeRing);
  const rangeActive = rangeRingDroneIds.includes(uav.id);

  const handleWaypointClick = () => {
    setIsSettingWaypoint(!isSettingWaypoint);
  };

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      <button
        onClick={handleWaypointClick}
        style={{
          flex: 2,
          padding: '3px 6px',
          border: `1px solid ${isSettingWaypoint ? 'rgba(34, 197, 94, 0.5)' : 'rgba(255,255,255,0.2)'}`,
          borderRadius: 3,
          background: isSettingWaypoint ? 'rgba(34, 197, 94, 0.2)' : 'transparent',
          color: isSettingWaypoint ? '#22c55e' : '#94a3b8',
          fontSize: '0.65rem',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        {isSettingWaypoint ? 'Select Target...' : 'Set Waypoint'}
      </button>

      <button
        onClick={() => toggleRangeRing(uav.id)}
        style={{
          flex: 1,
          padding: '3px 6px',
          border: `1px solid ${rangeActive ? 'rgba(251, 191, 36, 0.5)' : 'rgba(255,255,255,0.15)'}`,
          borderRadius: 3,
          background: rangeActive ? 'rgba(251, 191, 36, 0.2)' : 'transparent',
          color: rangeActive ? '#fbbf24' : '#64748b',
          fontSize: '0.65rem',
          cursor: 'pointer',
        }}
      >
        Range
      </button>

      <button
        onClick={() => {}}
        style={{
          width: 28,
          padding: '3px',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 3,
          background: 'transparent',
          color: '#64748b',
          fontSize: '0.75rem',
          cursor: 'pointer',
        }}
        title="Detail"
      >
        {'\u{1F3AF}'}
      </button>
    </div>
  );
}
