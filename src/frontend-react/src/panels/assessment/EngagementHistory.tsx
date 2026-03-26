import React, { useMemo } from 'react';
import { Tag } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';

interface EngagementRecord {
  id: string;
  timestamp: string;
  targetType: string;
  weapon: string;
  bdaConfidence: number;
  outcome: 'DESTROYED' | 'DAMAGED' | 'MISSED' | 'PENDING';
}

function outcomeColor(outcome: EngagementRecord['outcome']): string {
  switch (outcome) {
    case 'DESTROYED': return '#22c55e';
    case 'DAMAGED':   return '#f59e0b';
    case 'MISSED':    return '#ef4444';
    case 'PENDING':   return '#94a3b8';
    default:          return '#64748b';
  }
}

function bdaBar(confidence: number): React.ReactNode {
  const pct = Math.round(confidence * 100);
  const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{
        height: 3,
        width: 50,
        background: 'rgba(255,255,255,0.1)',
        borderRadius: 2,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: color,
          borderRadius: 2,
          transition: 'width 0.3s',
        }} />
      </div>
      <span style={{ fontSize: 10, color, fontFamily: 'monospace' }}>{pct}%</span>
    </div>
  );
}

export function EngagementHistory() {
  const commandEvents = useSimStore(s => s.commandEvents);
  const strikeBoard = useSimStore(s => s.strikeBoard);

  const engagements = useMemo<EngagementRecord[]>(() => {
    const records: EngagementRecord[] = [];

    for (const ev of commandEvents) {
      if (ev.action !== 'authorize_coa' && ev.action !== 'engagement_result') continue;

      const entry = ev.entry_id ? strikeBoard.find(e => e.id === ev.entry_id) : null;

      records.push({
        id: ev.entry_id || `${ev.timestamp}-${ev.action}`,
        timestamp: ev.timestamp,
        targetType: entry?.target_type || 'UNKNOWN',
        weapon: ev.coa_id ? `COA-${ev.coa_id.slice(-6)}` : 'UNKNOWN',
        bdaConfidence: entry?.detection_confidence ?? 0.5,
        outcome: ev.action === 'engagement_result'
          ? (((ev as Record<string, unknown>).outcome as EngagementRecord['outcome']) || 'DESTROYED')
          : 'PENDING',
      });
    }

    return records.slice().reverse();
  }, [commandEvents, strikeBoard]);

  if (engagements.length === 0) {
    return (
      <div style={{ padding: '8px 0', color: '#64748b', fontSize: '0.75rem', fontStyle: 'italic' }}>
        No engagement history.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {/* Header row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '80px 1fr 90px 70px 50px',
        gap: 6,
        padding: '3px 8px',
        fontSize: 9,
        fontWeight: 700,
        color: '#475569',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <span>TIME</span>
        <span>TARGET</span>
        <span>WEAPON</span>
        <span>BDA</span>
        <span>OUTCOME</span>
      </div>

      {engagements.map(rec => {
        const color = outcomeColor(rec.outcome);
        const time = new Date(rec.timestamp).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });

        return (
          <div
            key={rec.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '80px 1fr 90px 70px 50px',
              gap: 6,
              padding: '5px 8px',
              borderBottom: '1px solid rgba(255,255,255,0.03)',
              alignItems: 'center',
              background: 'rgba(255,255,255,0.01)',
            }}
          >
            <span style={{ fontSize: 10, color: '#475569', fontFamily: 'monospace' }}>{time}</span>
            <span style={{ fontSize: 11, color: '#cbd5e1', fontWeight: 500 }}>{rec.targetType}</span>
            <span style={{
              fontSize: 10,
              color: '#64748b',
              fontFamily: 'monospace',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {rec.weapon}
            </span>
            <div>{bdaBar(rec.bdaConfidence)}</div>
            <Tag
              minimal
              style={{
                background: `${color}22`,
                color: color,
                fontSize: 9,
                padding: '1px 4px',
                border: `1px solid ${color}44`,
              }}
            >
              {rec.outcome}
            </Tag>
          </div>
        );
      })}
    </div>
  );
}
