import React from 'react';
import { HTMLTable, Tag, Intent } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';

export function ISRQueue() {
  const isrQueue = useSimStore(s => s.isrQueue);

  if (isrQueue.length === 0) {
    return <div className="bp5-text-muted" style={{ padding: 16, fontSize: 12 }}>No ISR requirements.</div>;
  }

  return (
    <div style={{ padding: '8px 0' }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, padding: '0 16px', letterSpacing: '0.05em' }}>ISR QUEUE</div>
      <HTMLTable striped style={{ width: '100%' }}>
        <thead>
          <tr>
            <th style={{ padding: '4px 8px' }}>Target</th>
            <th style={{ padding: '4px 8px' }}>Type</th>
            <th style={{ padding: '4px 8px' }}>Urgency</th>
            <th style={{ padding: '4px 8px' }}>Gap</th>
            <th style={{ padding: '4px 8px' }}>Sensors Needed</th>
          </tr>
        </thead>
        <tbody>
          {isrQueue.map(req => (
            <tr key={req.target_id}>
              <td style={{ padding: '2px 8px' }}>TGT-{req.target_id}</td>
              <td style={{ padding: '2px 8px' }}><Tag minimal>{req.target_type}</Tag></td>
              <td style={{ padding: '2px 8px' }}>
                <Tag
                  intent={req.urgency_score > 0.7 ? Intent.DANGER : req.urgency_score > 0.4 ? Intent.WARNING : Intent.NONE}
                  minimal
                >
                  {(req.urgency_score * 100).toFixed(0)}%
                </Tag>
              </td>
              <td style={{ padding: '2px 8px' }}>{(req.verification_gap * 100).toFixed(0)}%</td>
              <td style={{ padding: '2px 8px' }}>{req.missing_sensor_types.join(', ') || 'None'}</td>
            </tr>
          ))}
        </tbody>
      </HTMLTable>
    </div>
  );
}
