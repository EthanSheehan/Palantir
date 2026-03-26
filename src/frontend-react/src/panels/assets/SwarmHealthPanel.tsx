import React, { useState } from 'react';
import { useSimStore } from '../../store/SimulationStore';
import { MODE_STYLES } from '../../shared/constants';
import { UAV } from '../../store/types';

const SENSOR_ICONS: Record<string, string> = {
  EO_IR:  '👁',
  SAR:    '📡',
  SIGINT: '📶',
  FUSION: '⚡',
};

// Fallback text labels when icons aren't wanted
const SENSOR_LABELS: Record<string, string> = {
  EO_IR:  'EO',
  SAR:    'SAR',
  SIGINT: 'SIG',
  FUSION: 'FSN',
};

function fuelBorderColor(fuelHours: number): string {
  if (fuelHours > 50) return '#22c55e';
  if (fuelHours > 25) return '#eab308';
  return '#ef4444';
}

interface DroneCell {
  uav: UAV;
  isSelected: boolean;
  isTracked: boolean;
  onClick: () => void;
}

function DroneCell({ uav, isSelected, isTracked, onClick }: DroneCell) {
  const modeStyle = MODE_STYLES[uav.mode] || { color: '#94a3b8', label: uav.mode };
  const borderColor = isSelected || isTracked ? '#facc15' : fuelBorderColor(uav.fuel_hours);
  const borderWidth = isSelected || isTracked ? 2 : 2;

  const sensorKey = (uav.sensor_type || '').toUpperCase();
  const sensorLabel = SENSOR_LABELS[sensorKey] || sensorKey.slice(0, 3) || '?';

  const cellStyle: React.CSSProperties = {
    width: 60,
    height: 60,
    border: `${borderWidth}px solid ${borderColor}`,
    borderRadius: 4,
    background: `${modeStyle.color}22`,
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
    position: 'relative',
    userSelect: 'none',
    transition: 'border-color 0.15s, background 0.15s',
    boxSizing: 'border-box',
  };

  return (
    <div style={cellStyle} onClick={onClick} title={`UAV-${uav.id} | ${uav.mode} | ${sensorKey} | Fuel: ${uav.fuel_hours.toFixed(0)}h`}>
      <span style={{ fontSize: '0.65rem', fontWeight: 700, color: modeStyle.color, lineHeight: 1 }}>
        D{uav.id}
      </span>
      <div style={{
        width: 20,
        height: 4,
        borderRadius: 2,
        background: `${modeStyle.color}66`,
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${Math.min(100, uav.fuel_hours)}%`,
          height: '100%',
          background: fuelBorderColor(uav.fuel_hours),
          borderRadius: 2,
        }} />
      </div>
      <span style={{ fontSize: '0.5rem', color: '#94a3b8', lineHeight: 1 }}>
        {sensorLabel}
      </span>
    </div>
  );
}

export function SwarmHealthPanel() {
  const uavs = useSimStore(s => s.uavs);
  const selectedDroneId = useSimStore(s => s.selectedDroneId);
  const trackedDroneId = useSimStore(s => s.trackedDroneId);
  const selectDrone = useSimStore(s => s.selectDrone);
  const setTrackedDrone = useSimStore(s => s.setTrackedDrone);
  const setDroneCamVisible = useSimStore(s => s.setDroneCamVisible);
  const [collapsed, setCollapsed] = useState(false);

  if (uavs.length === 0) return null;

  const handleCellClick = (uav: UAV) => {
    const isTracked = uav.id === trackedDroneId;
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

  const modeCount: Record<string, number> = {};
  for (const uav of uavs) {
    modeCount[uav.mode] = (modeCount[uav.mode] || 0) + 1;
  }

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 4,
      marginBottom: 8,
    }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setCollapsed(c => !c)}
      >
        <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', letterSpacing: '0.08em' }}>
          SWARM OVERVIEW — {uavs.length} UAV{uavs.length !== 1 ? 's' : ''}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {Object.entries(modeCount).slice(0, 4).map(([mode, count]) => {
            const style = MODE_STYLES[mode] || { color: '#94a3b8' };
            return (
              <span key={mode} style={{ fontSize: '0.6rem', color: style.color }}>
                {count} {mode}
              </span>
            );
          })}
          <span style={{ color: '#64748b', fontSize: '0.7rem', marginLeft: 4 }}>
            {collapsed ? '▸' : '▾'}
          </span>
        </div>
      </div>

      {!collapsed && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 4,
          padding: '4px 8px 8px 8px',
        }}>
          {uavs.map(uav => (
            <DroneCell
              key={uav.id}
              uav={uav}
              isSelected={uav.id === selectedDroneId}
              isTracked={uav.id === trackedDroneId}
              onClick={() => handleCellClick(uav)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
