import React, { useEffect, useState } from 'react';
import { Button, Icon, IconName, InputGroup, Intent } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { useSendMessage } from '../App';

/**
 * TwoPersonConcurrencePanel — operator surface for the FedRAMP-High
 * two-person concurrence control. Beyond-Maven differentiator: Maven
 * dispatches AUTONOMOUS engagements on a single operator's authority;
 * we require a second concur within 5 minutes.
 *
 * Workflow:
 *   1. Operator A selects a target and clicks "Request concurrence" with
 *      their operator ID + rationale → CONCURRENCE_REQUESTED ack.
 *   2. Operator B (different ID, same WebSocket session in this demo)
 *      clicks "Concur" with their operator ID → CONCURRENCE_GRANTED.
 *   3. Effectors agent consumes the authorisation on the next AUTONOMOUS
 *      engagement.
 *
 * Real deployment: each operator has their own session + JWT; the panel
 * shows pending requests across the cluster and B explicitly endorses.
 * Demo: single session, two ID fields, immediate feedback.
 */

interface ConcurrenceState {
  pending: boolean;
  granted: boolean;
  primary?: string;
  secondary?: string;
  latency_sec?: number;
  error?: string;
}

interface Props { visible: boolean; onClose: () => void; }

export function TwoPersonConcurrencePanel({ visible, onClose }: Props) {
  const sendMessage = useSendMessage();
  const targets = useSimStore(s => s.targets);
  const selectedId = useSimStore(s => s.selectedTargetId);
  const target = targets.find(t => t.id === selectedId);

  const [primaryId, setPrimaryId] = useState('alice');
  const [secondaryId, setSecondaryId] = useState('bob');
  const [rationale, setRationale] = useState('Sustained verified track w/ multi-INT corroboration');
  const [state, setState] = useState<ConcurrenceState>({ pending: false, granted: false });

  useEffect(() => {
    function onRequested(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.target_id === target?.id) {
        setState(s => ({ ...s, pending: true, primary: detail.primary_operator_id, error: undefined }));
      }
    }
    function onGranted(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.target_id === target?.id) {
        setState({
          pending: false,
          granted: true,
          primary: detail.primary_operator_id,
          secondary: detail.secondary_operator_id,
          latency_sec: detail.latency_sec,
        });
      }
    }
    function onError(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.action && detail.action.startsWith('record_concurrence')) {
        setState(s => ({ ...s, error: detail.error || 'concurrence rejected' }));
      }
    }
    window.addEventListener('grid-sentinel:concurrence-requested', onRequested);
    window.addEventListener('grid-sentinel:concurrence-granted', onGranted);
    window.addEventListener('grid-sentinel:error', onError);
    return () => {
      window.removeEventListener('grid-sentinel:concurrence-requested', onRequested);
      window.removeEventListener('grid-sentinel:concurrence-granted', onGranted);
      window.removeEventListener('grid-sentinel:error', onError);
    };
  }, [target?.id]);

  if (!visible) return null;

  const requestConcurrence = () => {
    if (!target) return;
    setState({ pending: false, granted: false });
    sendMessage({
      action: 'request_concurrence',
      target_id: target.id,
      primary_operator_id: primaryId,
      rationale,
    });
  };

  const recordConcurrence = () => {
    if (!target) return;
    sendMessage({
      action: 'record_concurrence',
      target_id: target.id,
      secondary_operator_id: secondaryId,
    });
  };

  return (
    <div
      role="dialog"
      aria-label="Two-person concurrence"
      className="gs-glass-tinted"
      style={{
        position: 'fixed',
        right: 12,
        top: 80,
        width: 380,
        maxHeight: 'calc(100vh - 100px)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 4,
        zIndex: 8400,
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
          <Icon icon={'shield' as IconName} size={12} color="#fbbf24" />
          <span style={{
            fontFamily: 'monospace', fontWeight: 700, fontSize: 11,
            letterSpacing: '0.16em', color: '#e2e8f0',
          }}>
            TWO-PERSON CONCURRENCE
          </span>
        </div>
        <Button minimal small icon={'cross' as IconName} onClick={onClose} aria-label="Close" />
      </div>

      <div style={{ padding: 10, fontSize: 11, color: '#cbd5e1', overflowY: 'auto' }}>
        <div style={{
          fontSize: 9, color: '#94a3b8', letterSpacing: '0.12em',
          marginBottom: 8,
        }}>
          FedRAMP-High control: AUTONOMOUS engagements require two distinct
          operators within a 5-minute window.
        </div>

        {!target ? (
          <div style={{ color: '#64748b', fontStyle: 'italic' }}>
            Select a target first. Concurrence is target-scoped.
          </div>
        ) : (
          <>
            <div style={{
              padding: '6px 8px', marginBottom: 10,
              background: 'rgba(34, 211, 238, 0.06)',
              border: '1px solid rgba(34, 211, 238, 0.18)',
              borderRadius: 3,
            }}>
              Target #{String(target.id).padStart(4, '0')} ·
              <span style={{ color: '#22d3ee', marginLeft: 4 }}>{target.type}</span> ·
              state {target.state}
            </div>

            <div style={{ marginBottom: 8 }}>
              <label style={{ fontSize: 9, color: '#94a3b8', letterSpacing: '0.1em' }}>
                PRIMARY OPERATOR ID
              </label>
              <InputGroup
                small
                value={primaryId}
                onChange={(e: any) => setPrimaryId(e.target.value)}
                placeholder="alice"
                style={{ marginTop: 2 }}
              />
            </div>

            <div style={{ marginBottom: 8 }}>
              <label style={{ fontSize: 9, color: '#94a3b8', letterSpacing: '0.1em' }}>
                RATIONALE
              </label>
              <InputGroup
                small
                value={rationale}
                onChange={(e: any) => setRationale(e.target.value)}
                style={{ marginTop: 2 }}
              />
            </div>

            <Button
              small fill intent={Intent.WARNING}
              icon={'flag' as IconName}
              text={state.pending ? 'CONCURRENCE PENDING…' : 'REQUEST CONCURRENCE'}
              onClick={requestConcurrence}
              disabled={state.pending}
              style={{ marginBottom: 12 }}
            />

            <div style={{
              borderTop: '1px solid rgba(255,255,255,0.08)',
              paddingTop: 10, marginTop: 4,
            }}>
              <div style={{ fontSize: 9, color: '#94a3b8', letterSpacing: '0.1em', marginBottom: 4 }}>
                SECONDARY OPERATOR ID
              </div>
              <InputGroup
                small
                value={secondaryId}
                onChange={(e: any) => setSecondaryId(e.target.value)}
                placeholder="bob"
                style={{ marginBottom: 6 }}
              />
              <Button
                small fill intent={Intent.SUCCESS}
                icon={'tick-circle' as IconName}
                text="CONCUR"
                onClick={recordConcurrence}
                disabled={!state.pending}
              />
            </div>

            {state.granted && (
              <div style={{
                marginTop: 12,
                padding: '6px 8px',
                background: 'rgba(34, 197, 94, 0.10)',
                border: '1px solid rgba(34, 197, 94, 0.35)',
                borderRadius: 3,
              }}>
                <div style={{ fontWeight: 700, color: '#22c55e' }}>
                  ✓ Concurrence granted
                </div>
                <div style={{ fontSize: 10, color: '#cbd5e1', marginTop: 2 }}>
                  {state.primary} → {state.secondary} ·
                  latency {state.latency_sec?.toFixed(2)}s
                </div>
                <div style={{ fontSize: 9, color: '#94a3b8', marginTop: 4, fontStyle: 'italic' }}>
                  Authorisation is single-shot — next AUTONOMOUS engagement
                  on this target will consume it.
                </div>
              </div>
            )}

            {state.error && (
              <div style={{
                marginTop: 12,
                padding: '6px 8px',
                background: 'rgba(239, 68, 68, 0.10)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: 3,
                color: '#fca5a5',
                fontSize: 10,
              }}>
                ⚠ {state.error}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
