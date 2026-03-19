import React from 'react';
import { UAV } from '../../store/types';
import { DroneModeButtons } from './DroneModeButtons';
import { DroneActionButtons } from './DroneActionButtons';

interface DroneCardDetailsProps {
  uav: UAV;
}

const labelStyle: React.CSSProperties = {
  color: '#64748b',
  fontSize: '0.7rem',
  minWidth: 80,
};

const valueStyle: React.CSSProperties = {
  color: '#cbd5e1',
  fontSize: '0.7rem',
};

export function DroneCardDetails({ uav }: DroneCardDetailsProps) {
  const altKm = ((uav.altitude_m || 1000) / 1000).toFixed(2);
  const sensorStr = uav.sensor_type || 'EO/IR';
  const trackedTgt = uav.tracked_target_id ? `TGT-${uav.tracked_target_id}` : '--';

  const stats = [
    ['Altitude:', `${altKm} km`],
    ['Sensor:', sensorStr],
    ['Tracking:', trackedTgt],
    ['Coordinates:', `${uav.lon.toFixed(4)}, ${uav.lat.toFixed(4)}`],
  ];

  return (
    <div style={{ marginTop: 8 }} onClick={e => e.stopPropagation()}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 8 }}>
        {stats.map(([label, value]) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={labelStyle}>{label}</span>
            <span style={valueStyle}>{value}</span>
          </div>
        ))}
      </div>
      <DroneModeButtons uav={uav} />
      <DroneActionButtons uav={uav} />
    </div>
  );
}
