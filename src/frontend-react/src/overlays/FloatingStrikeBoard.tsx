import React, { useEffect, useRef, useState } from 'react';
import { Button, Intent, Tag } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { useSendMessage } from '../App';
import { StrikeEntry } from '../store/types';

interface Props {
  visible: boolean;
  onToggle: () => void;
}

function useCountdown(expiresAt: number): number {
  const [remaining, setRemaining] = useState(() => Math.max(0, expiresAt - Date.now() / 1000));
  useEffect(() => {
    const interval = setInterval(() => {
      setRemaining(Math.max(0, expiresAt - Date.now() / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [expiresAt]);
  return remaining;
}

interface NominationRowProps {
  entry: StrikeEntry;
}

function NominationRow({ entry }: NominationRowProps) {
  const sendMessage = useSendMessage();
  // Approximate expiry: nominations time out after 300s from now if no metadata
  const expiresAt = useRef(Date.now() / 1000 + 300).current;
  const remaining = useCountdown(expiresAt);

  const urgency = remaining < 60 ? '#ef4444' : remaining < 120 ? '#eab308' : '#22c55e';

  return (
    <div
      style={{
        padding: '8px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        borderLeft: `2px solid #eab308`,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>{entry.target_type}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, color: urgency, fontWeight: 700 }}>
            {Math.floor(remaining / 60)}:{String(Math.floor(remaining % 60)).padStart(2, '0')}
          </span>
          <Tag minimal style={{ fontSize: 9, background: '#eab30822', color: '#eab308', border: '1px solid #eab30844' }}>
            PENDING
          </Tag>
        </div>
      </div>

      <div style={{ fontSize: 10, color: '#64748b', display: 'flex', gap: 10, marginBottom: 6 }}>
        <span>Conf: {Math.round(entry.detection_confidence * 100)}%</span>
        <span>P: {entry.priority_score}</span>
        <span>ROE: {entry.roe_evaluation}</span>
        <span style={{ color: '#475569' }}>#{entry.id.slice(0, 8)}</span>
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <Button
          intent={Intent.SUCCESS}
          small
          minimal
          text="APPROVE"
          style={{ fontSize: 10 }}
          onClick={() => sendMessage({ action: 'approve_nomination', entry_id: entry.id, rationale: 'Approved via overlay' })}
        />
        <Button
          intent={Intent.DANGER}
          small
          minimal
          text="REJECT"
          style={{ fontSize: 10 }}
          onClick={() => sendMessage({ action: 'reject_nomination', entry_id: entry.id, rationale: 'Rejected via overlay' })}
        />
        <Button
          intent={Intent.WARNING}
          small
          minimal
          text="RETASK"
          style={{ fontSize: 10 }}
          onClick={() => sendMessage({ action: 'retask_nomination', entry_id: entry.id, rationale: 'Retasked via overlay' })}
        />
      </div>
    </div>
  );
}

function CompactEntry({ entry }: { entry: StrikeEntry }) {
  const STATUS_COLORS: Record<string, string> = {
    APPROVED: '#22c55e', REJECTED: '#ef4444', RETASKED: '#3b82f6',
  };
  const color = STATUS_COLORS[entry.status] ?? '#94a3b8';
  return (
    <div style={{
      padding: '5px 12px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      display: 'flex',
      alignItems: 'center',
      gap: 8,
    }}>
      <span style={{ fontSize: 11, color: '#94a3b8', flex: 1 }}>{entry.target_type}</span>
      <Tag minimal style={{ fontSize: 9, background: `${color}22`, color, border: `1px solid ${color}44` }}>
        {entry.status}
      </Tag>
    </div>
  );
}

export function FloatingStrikeBoard({ visible, onToggle }: Props) {
  const strikeBoard = useSimStore(s => s.strikeBoard);

  const pending = strikeBoard.filter(e => e.status === 'PENDING');
  const resolved = strikeBoard.filter(e => e.status !== 'PENDING').slice(-6);

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 80,
        right: 20,
        zIndex: 8800,
        width: 320,
        maxHeight: 500,
        background: 'rgba(13,17,26,0.97)',
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 6,
        boxShadow: '0 16px 48px rgba(0,0,0,0.7)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        fontFamily: 'monospace',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 12px',
        background: pending.length > 0 ? 'rgba(234,179,8,0.08)' : 'transparent',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Strike Board
          </span>
          {pending.length > 0 && (
            <span style={{
              fontSize: 9, fontWeight: 700,
              background: '#eab308',
              color: '#000',
              padding: '1px 6px',
              borderRadius: 3,
            }}>
              {pending.length} PENDING
            </span>
          )}
        </div>
        <button
          onClick={onToggle}
          style={{ background: 'none', border: 'none', color: '#475569', fontSize: 14, cursor: 'pointer', lineHeight: 1 }}
        >
          ×
        </button>
      </div>

      <div style={{ overflowY: 'auto', flex: 1 }}>
        {strikeBoard.length === 0 ? (
          <div style={{ padding: 20, color: '#475569', fontSize: 12, textAlign: 'center' }}>
            No strike packages
          </div>
        ) : (
          <>
            {pending.length > 0 && (
              <>
                <div style={{ padding: '5px 12px 2px', color: '#475569', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  Pending Nominations
                </div>
                {pending.map(entry => (
                  <NominationRow key={entry.id} entry={entry} />
                ))}
              </>
            )}
            {resolved.length > 0 && (
              <>
                <div style={{ padding: '5px 12px 2px', color: '#334155', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  Recent
                </div>
                {resolved.map(entry => (
                  <CompactEntry key={entry.id} entry={entry} />
                ))}
              </>
            )}
          </>
        )}
      </div>

      <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '4px 12px', color: '#334155', fontSize: 9 }}>
        Press B to toggle · {strikeBoard.length} total entries
      </div>
    </div>
  );
}
