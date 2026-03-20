import React from 'react';
import { Card, Tag, HTMLTable } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';

export function CommandLog() {
  const events = useSimStore(s => s.commandEvents);

  if (events.length === 0) return null;

  return (
    <Card style={{ padding: 8 }}>
      <div style={{ fontWeight: 700, fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>
        COMMAND LOG
      </div>
      <div style={{ maxHeight: 200, overflowY: 'auto' }}>
        <HTMLTable style={{ width: '100%', fontSize: 11 }}>
          <tbody>
            {events.slice().reverse().map((e, i) => (
              <tr key={i}>
                <td style={{ color: '#475569', padding: '2px 4px' }}>
                  {e.timestamp?.slice(11, 19)}
                </td>
                <td style={{ padding: '2px 4px' }}>
                  <Tag minimal style={{ fontSize: 10 }}>{e.action}</Tag>
                </td>
                <td style={{ color: '#94a3b8', padding: '2px 4px' }}>
                  {e.source || 'operator'}
                </td>
              </tr>
            ))}
          </tbody>
        </HTMLTable>
      </div>
    </Card>
  );
}
