import React from 'react';
import { Card, Tag, Intent } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';

const FEED_INTENT: Record<string, Intent> = {
  DETECTED: Intent.PRIMARY,
  CLASSIFIED: Intent.WARNING,
  VERIFIED: Intent.SUCCESS,
  NOMINATED: Intent.DANGER,
  state_transition: Intent.NONE,
};

export function IntelFeed() {
  const events = useSimStore(s => s.intelEvents);

  if (events.length === 0) return null;

  return (
    <Card style={{ padding: 8 }}>
      <div style={{ fontWeight: 700, fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>
        INTEL FEED
      </div>
      <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
        {events.slice().reverse().map((e, i) => (
          <div key={i} style={{ fontSize: 11, display: 'flex', gap: 6, alignItems: 'flex-start' }}>
            <span style={{ color: '#475569', flexShrink: 0 }}>
              {e.timestamp?.slice(11, 19)}
            </span>
            <Tag minimal intent={FEED_INTENT[e.event] || Intent.NONE} style={{ fontSize: 10 }}>
              {e.event}
            </Tag>
            <span style={{ color: '#94a3b8' }}>{e.summary}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
