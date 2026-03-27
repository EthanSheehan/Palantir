import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Tag } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';

type AlertType = 'NOMINATION' | 'ENGAGEMENT' | 'TRANSITION' | 'CONNECTION' | 'CRITICAL';

interface Alert {
  id: string;
  type: AlertType;
  message: string;
  timestamp: number;
  autoDismiss: boolean;
  actionLabel?: string;
  actionTab?: string;
}

const TYPE_ICONS: Record<AlertType, string> = {
  NOMINATION: '⚠',
  ENGAGEMENT: '🎯',
  TRANSITION: '↔',
  CONNECTION: '⚡',
  CRITICAL: '🔴',
};

const TYPE_COLORS: Record<AlertType, string> = {
  NOMINATION: '#eab308',
  ENGAGEMENT: '#ef4444',
  TRANSITION: '#3b82f6',
  CONNECTION: '#f97316',
  CRITICAL: '#dc2626',
};

function makeId() {
  return Math.random().toString(36).slice(2, 9);
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

interface Props {
  visible: boolean;
  onToggle: () => void;
}

export function GlobalAlertCenter({ visible, onToggle }: Props) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const strikeBoard = useSimStore(s => s.strikeBoard);
  const commandEvents = useSimStore(s => s.commandEvents);
  const pendingTransitions = useSimStore(s => s.pendingTransitions);
  const connected = useSimStore(s => s.connected);
  const setActiveTab = useSimStore(s => s.setActiveTab);

  const prevConnected = useRef(connected);
  const prevCommandCount = useRef(0);
  const seenNominationIds = useRef<Set<string>>(new Set());
  const seenTransitionDroneIds = useRef<Set<string>>(new Set());

  const addAlert = useCallback((alert: Omit<Alert, 'id' | 'timestamp'>) => {
    const newAlert: Alert = { ...alert, id: makeId(), timestamp: Date.now() };
    setAlerts(prev => [newAlert, ...prev].slice(0, 20));
  }, []);

  function dismiss(id: string) {
    setAlerts(prev => prev.filter(a => a.id !== id));
  }

  // Connection drop alerts
  useEffect(() => {
    if (prevConnected.current && !connected) {
      addAlert({ type: 'CONNECTION', message: 'WebSocket connection lost — attempting reconnect', autoDismiss: false });
    } else if (!prevConnected.current && connected) {
      addAlert({ type: 'CONNECTION', message: 'WebSocket connection restored', autoDismiss: true });
    }
    prevConnected.current = connected;
  }, [connected, addAlert]);

  // Pending nomination alerts — deduplicate by entry ID
  useEffect(() => {
    const pending = strikeBoard.filter(e => e.status === 'PENDING');
    for (const entry of pending) {
      const entryId = entry.id;
      if (entryId && !seenNominationIds.current.has(entryId)) {
        seenNominationIds.current.add(entryId);
        addAlert({
          type: 'NOMINATION',
          message: `New nomination: ${entry.target_type} (conf ${Math.round(entry.detection_confidence * 100)}%)`,
          autoDismiss: false,
          actionLabel: 'Review',
          actionTab: 'mission',
        });
      }
    }
  }, [strikeBoard, addAlert]);

  // Engagement result alerts from command events
  useEffect(() => {
    if (commandEvents.length > prevCommandCount.current) {
      const newEvents = commandEvents.slice(prevCommandCount.current);
      for (const ev of newEvents) {
        if (ev.action === 'authorize_coa' || ev.action === 'approve_nomination') {
          addAlert({
            type: 'ENGAGEMENT',
            message: `${ev.action.replace(/_/g, ' ').toUpperCase()} — target ${ev.target_id ?? ev.entry_id ?? '?'}`,
            autoDismiss: true,
            actionLabel: 'Strike Board',
            actionTab: 'mission',
          });
        }
      }
      prevCommandCount.current = commandEvents.length;
    }
  }, [commandEvents, addAlert]);

  // Autonomy transition alerts — deduplicate by drone ID
  useEffect(() => {
    const currentDroneIds = new Set(Object.keys(pendingTransitions));
    for (const [droneId, trans] of Object.entries(pendingTransitions)) {
      if (!seenTransitionDroneIds.current.has(droneId)) {
        seenTransitionDroneIds.current.add(droneId);
        addAlert({
          type: 'TRANSITION',
          message: `UAV ${droneId} awaiting transition to ${trans.mode}: ${trans.reason}`,
          autoDismiss: false,
          actionLabel: 'Assets',
          actionTab: 'assets',
        });
      }
    }
    // Clear seen IDs for drones that are no longer pending
    for (const id of seenTransitionDroneIds.current) {
      if (!currentDroneIds.has(id)) seenTransitionDroneIds.current.delete(id);
    }
  }, [pendingTransitions, addAlert]);

  // Auto-dismiss non-critical alerts after 10s — single long-lived interval
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      setAlerts(prev => {
        const filtered = prev.filter(a => !a.autoDismiss || now - a.timestamp < 10_000);
        return filtered.length === prev.length ? prev : filtered;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const unread = alerts.length;

  return (
    <>
      {/* Floating badge button */}
      <div
        onClick={onToggle}
        style={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          zIndex: 8900,
          width: 44,
          height: 44,
          borderRadius: '50%',
          background: unread > 0 ? 'rgba(220,38,38,0.9)' : 'rgba(30,40,55,0.92)',
          border: `1px solid ${unread > 0 ? '#dc2626' : 'rgba(255,255,255,0.15)'}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          boxShadow: unread > 0 ? '0 0 12px rgba(220,38,38,0.5)' : '0 2px 8px rgba(0,0,0,0.5)',
          transition: 'all 0.2s',
          fontFamily: 'monospace',
        }}
        title="Global Alert Center (G)"
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: '#fff' }}>
          {unread > 0 ? (unread > 99 ? '99+' : unread) : '🔔'}
        </span>
      </div>

      {/* Alert panel */}
      {visible && (
        <div
          style={{
            position: 'fixed',
            bottom: 72,
            right: 20,
            zIndex: 8900,
            width: 360,
            maxHeight: 480,
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
            borderBottom: '1px solid rgba(255,255,255,0.08)',
          }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Global Alert Center
            </span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {alerts.length > 0 && (
                <button
                  onClick={() => setAlerts([])}
                  style={{
                    background: 'none', border: 'none', color: '#475569', fontSize: 10,
                    cursor: 'pointer', padding: '2px 4px',
                  }}
                >
                  Clear all
                </button>
              )}
              <button
                onClick={onToggle}
                style={{ background: 'none', border: 'none', color: '#475569', fontSize: 14, cursor: 'pointer', lineHeight: 1 }}
              >
                ×
              </button>
            </div>
          </div>

          {/* Alert list */}
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {alerts.length === 0 ? (
              <div style={{ padding: 20, color: '#475569', fontSize: 12, textAlign: 'center' }}>
                No alerts
              </div>
            ) : (
              alerts.map(alert => (
                <AlertRow
                  key={alert.id}
                  alert={alert}
                  onDismiss={dismiss}
                  onAction={(tab) => { setActiveTab(tab); onToggle(); }}
                />
              ))
            )}
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '4px 12px', color: '#334155', fontSize: 9 }}>
            Press G to toggle · auto-dismiss non-critical after 10s
          </div>
        </div>
      )}
    </>
  );
}

interface AlertRowProps {
  alert: Alert;
  onDismiss: (id: string) => void;
  onAction: (tab: string) => void;
}

function AlertRow({ alert, onDismiss, onAction }: AlertRowProps) {
  const color = TYPE_COLORS[alert.type];
  const icon = TYPE_ICONS[alert.type];
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        padding: '8px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        borderLeft: `2px solid ${color}`,
      }}
    >
      <span style={{ fontSize: 13, flexShrink: 0, marginTop: 1 }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.4, wordBreak: 'break-word' }}>
          {alert.message}
        </div>
        <div style={{ fontSize: 9, color: '#475569', marginTop: 2 }}>
          {formatTime(alert.timestamp)}
          {' · '}
          <Tag
            minimal
            style={{ fontSize: 8, padding: '0 4px', color, background: `${color}22`, border: `1px solid ${color}44` }}
          >
            {alert.type}
          </Tag>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0 }}>
        {alert.actionLabel && alert.actionTab && (
          <Button
            small
            minimal
            onClick={() => onAction(alert.actionTab!)}
            style={{ fontSize: 9, padding: '1px 6px', color: '#3b82f6' }}
          >
            {alert.actionLabel}
          </Button>
        )}
        <button
          onClick={() => onDismiss(alert.id)}
          style={{ background: 'none', border: 'none', color: '#334155', fontSize: 12, cursor: 'pointer', lineHeight: 1, padding: 0 }}
        >
          ×
        </button>
      </div>
    </div>
  );
}
