import React, { useEffect, useState } from 'react';
import { Button, ButtonGroup, ProgressBar } from '@blueprintjs/core';
import { useSendMessage } from '../../App';

interface PendingTransition {
  mode: string;
  reason: string;
  expires_at: number;
}

interface TransitionToastProps {
  uavId: number;
  pending: PendingTransition;
}

const TOTAL_COUNTDOWN_SEC = 10;

export function TransitionToast({ uavId, pending }: TransitionToastProps) {
  const sendMessage = useSendMessage();

  const getRemainingSeconds = () =>
    Math.max(0, Math.round(pending.expires_at - Date.now() / 1000));

  const [remaining, setRemaining] = useState(getRemainingSeconds);

  useEffect(() => {
    setRemaining(getRemainingSeconds());
    const interval = setInterval(() => {
      setRemaining(getRemainingSeconds());
    }, 1000);
    return () => clearInterval(interval);
  }, [pending.expires_at]);

  const handleApprove = (e: React.MouseEvent) => {
    e.stopPropagation();
    sendMessage({ action: 'approve_transition', drone_id: uavId });
  };

  const handleReject = (e: React.MouseEvent) => {
    e.stopPropagation();
    sendMessage({ action: 'reject_transition', drone_id: uavId });
  };

  const progressValue = Math.max(0, Math.min(1, remaining / TOTAL_COUNTDOWN_SEC));

  return (
    <div
      style={{
        marginTop: 6,
        borderRadius: 3,
        borderLeft: '3px solid #d97008',
        background: 'rgba(217, 112, 8, 0.08)',
        padding: '6px 8px',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
        <span style={{ fontWeight: 700, fontSize: '0.7rem', color: '#e2e8f0' }}>
          UAV-{uavId} &rarr; {pending.mode}
        </span>
      </div>
      <div style={{ color: '#94a3b8', fontSize: '0.65rem', marginBottom: 4 }}>
        {pending.reason}
      </div>

      {remaining > 0 ? (
        <>
          <div style={{ marginBottom: 4 }}>
            <ProgressBar
              value={progressValue}
              intent="warning"
              stripes={false}
              animate={false}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.6rem', color: '#94a3b8' }}>
              Auto-approve in {remaining}s
            </span>
            <ButtonGroup minimal>
              <Button intent="success" small onClick={handleApprove}>
                Approve
              </Button>
              <Button intent="danger" small onClick={handleReject}>
                Reject
              </Button>
            </ButtonGroup>
          </div>
        </>
      ) : (
        <div style={{ fontSize: '0.65rem', color: '#94a3b8', fontStyle: 'italic' }}>
          Auto-approved
        </div>
      )}
    </div>
  );
}
