import React, { useEffect, useState } from 'react';
import { Button, Icon, IconName, Tag } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { useSendMessage } from '../App';

/**
 * ActivityTimeline — per-target chronological band of detection events,
 * verification state changes, COA history, and BDA outcomes.
 *
 * Reads from `kill_chain_tracker` + `audit_trail` via a new WebSocket action
 * `get_target_history`. Backend returns a sorted list of `{timestamp, kind,
 * label, detail}` events; the panel renders them as a vertical chrono-track.
 */

interface TimelineEvent {
  timestamp: number;
  kind: 'DETECTION' | 'STATE' | 'COA' | 'ENGAGEMENT' | 'BDA' | 'OPERATOR' | 'NOTE';
  label: string;
  detail?: string;
  source?: string;
}

const KIND_STYLE: Record<TimelineEvent['kind'], { color: string; icon: IconName }> = {
  DETECTION:  { color: '#22d3ee', icon: 'eye-on' },
  STATE:      { color: '#fbbf24', icon: 'flow-linear' },
  COA:        { color: '#a855f7', icon: 'route' },
  ENGAGEMENT: { color: '#ef4444', icon: 'flame' },
  BDA:        { color: '#06b6d4', icon: 'comparison' },
  OPERATOR:   { color: '#94a3b8', icon: 'user' },
  NOTE:       { color: '#475569', icon: 'comment' },
};

interface Props { visible: boolean; onClose: () => void; }

export function ActivityTimeline({ visible, onClose }: Props) {
  const sendMessage = useSendMessage();
  const targets = useSimStore(s => s.targets);
  const selectedId = useSimStore(s => s.selectedTargetId);
  const target = targets.find(t => t.id === selectedId);
  const [events, setEvents] = useState<TimelineEvent[]>([]);

  useEffect(() => {
    if (!visible || !target) {
      setEvents([]);
      return;
    }
    sendMessage({ action: 'get_target_history', target_id: target.id });
    function onResponse(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.target_id === target?.id && Array.isArray(detail.events)) {
        setEvents(detail.events);
      }
    }
    window.addEventListener('grid-sentinel:target-history', onResponse);
    return () => window.removeEventListener('grid-sentinel:target-history', onResponse);
  }, [visible, target?.id, sendMessage]);

  if (!visible) return null;

  return (
    <div
      role="region"
      aria-label="Activity timeline"
      style={{
        position: 'fixed',
        left: 80,
        top: 80,
        width: 380,
        maxHeight: 'calc(100vh - 100px)',
        background: 'rgba(7, 11, 17, 0.97)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 4,
        boxShadow: '8px 8px 32px rgba(0,0,0,0.55)',
        zIndex: 8200,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(15, 20, 30, 0.95)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon icon={'timeline-events' as IconName} size={12} color="#06b6d4" />
          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 11, letterSpacing: '0.16em', color: '#e2e8f0' }}>
            ACTIVITY TIMELINE
          </span>
          {target && (
            <Tag minimal style={{ background: '#06b6d422', color: '#06b6d4', border: '1px solid #06b6d455', fontSize: 9 }}>
              #{String(target.id).padStart(4, '0')} {target.type}
            </Tag>
          )}
        </div>
        <Button minimal small icon={'cross' as IconName} onClick={onClose} aria-label="Close" />
      </div>

      {!target ? (
        <div style={{ padding: 16, color: '#64748b', fontSize: 11, fontStyle: 'italic' }}>
          Select a target to view its activity history.
        </div>
      ) : events.length === 0 ? (
        <div style={{ padding: 16, color: '#64748b', fontSize: 11, fontStyle: 'italic' }}>
          No history yet for this target. Tactical events will appear here as they happen.
        </div>
      ) : (
        <div style={{ overflowY: 'auto', padding: '6px 10px', flex: 1 }}>
          {events.map((ev, i) => <EventRow key={i} ev={ev} />)}
        </div>
      )}
    </div>
  );
}

function EventRow({ ev }: { ev: TimelineEvent }) {
  const style = KIND_STYLE[ev.kind] ?? KIND_STYLE.NOTE;
  const t = new Date(ev.timestamp);
  return (
    <div style={{
      position: 'relative',
      paddingLeft: 22,
      paddingBottom: 10,
      borderLeft: `1px solid ${style.color}33`,
    }}>
      <div style={{
        position: 'absolute',
        left: -7,
        top: 0,
        width: 14,
        height: 14,
        borderRadius: '50%',
        background: '#0b0f17',
        border: `2px solid ${style.color}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <Icon icon={style.icon} size={8} color={style.color} />
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#475569' }}>
          {t.toLocaleTimeString()}
        </span>
        <Tag minimal style={{
          fontSize: 8,
          background: `${style.color}22`,
          color: style.color,
          border: `1px solid ${style.color}55`,
          padding: '0 4px',
          minHeight: 14,
        }}>{ev.kind}</Tag>
      </div>
      <div style={{ color: '#e2e8f0', fontSize: 11, marginTop: 2 }}>{ev.label}</div>
      {ev.detail && (
        <div style={{ color: '#94a3b8', fontSize: 10, marginTop: 2, lineHeight: 1.4 }}>{ev.detail}</div>
      )}
      {ev.source && (
        <div style={{ color: '#475569', fontSize: 9, marginTop: 1, fontFamily: 'monospace' }}>
          src: {ev.source}
        </div>
      )}
    </div>
  );
}
