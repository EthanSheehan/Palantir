import React, { useState } from 'react';
import { Button, Intent, Alert } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';
import { useSendMessage } from '../../App';
import { StrikeBoardEntry } from './StrikeBoardEntry';

const STATUS_ORDER: Record<string, number> = {
  PENDING: 0, APPROVED: 1, RETASKED: 2, REJECTED: 3,
};

type BatchAction = 'APPROVE_ALL' | 'REJECT_ALL' | null;

export function StrikeBoard() {
  const entries = useSimStore(s => s.strikeBoard);
  const sendMessage = useSendMessage();
  const [pendingAction, setPendingAction] = useState<BatchAction>(null);

  const sorted = [...entries].sort((a, b) =>
    (STATUS_ORDER[a.status] ?? 4) - (STATUS_ORDER[b.status] ?? 4)
  );

  const pendingEntries = entries.filter(e => e.status === 'PENDING');

  const handleBatchConfirm = () => {
    if (pendingAction === 'APPROVE_ALL') {
      for (const entry of pendingEntries) {
        sendMessage({ action: 'approve_nomination', entry_id: entry.id, rationale: 'Batch approved' });
      }
    } else if (pendingAction === 'REJECT_ALL') {
      for (const entry of pendingEntries) {
        sendMessage({ action: 'reject_nomination', entry_id: entry.id, rationale: 'Batch rejected' });
      }
    }
    setPendingAction(null);
  };

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.05em' }}>
          STRIKE BOARD
        </div>
        {pendingEntries.length > 0 && (
          <div style={{ display: 'flex', gap: 4 }}>
            <Button
              intent={Intent.SUCCESS}
              small
              minimal
              text={`APPROVE ALL (${pendingEntries.length})`}
              onClick={() => setPendingAction('APPROVE_ALL')}
              style={{ fontSize: 10 }}
            />
            <Button
              intent={Intent.DANGER}
              small
              minimal
              text="REJECT ALL"
              onClick={() => setPendingAction('REJECT_ALL')}
              style={{ fontSize: 10 }}
            />
          </div>
        )}
      </div>

      {sorted.length === 0 ? (
        <div style={{ color: '#94a3b8', fontSize: 12 }}>No active strike packages.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sorted.map(entry => (
            <StrikeBoardEntry key={entry.id} entry={entry} />
          ))}
        </div>
      )}

      <Alert
        isOpen={pendingAction !== null}
        intent={pendingAction === 'APPROVE_ALL' ? Intent.SUCCESS : Intent.DANGER}
        confirmButtonText={pendingAction === 'APPROVE_ALL' ? 'Approve All' : 'Reject All'}
        cancelButtonText="Cancel"
        onConfirm={handleBatchConfirm}
        onCancel={() => setPendingAction(null)}
        icon={pendingAction === 'APPROVE_ALL' ? 'tick-circle' : 'ban-circle'}
        className="bp5-dark"
      >
        <p style={{ fontSize: 13 }}>
          {pendingAction === 'APPROVE_ALL'
            ? `Approve all ${pendingEntries.length} pending nomination(s)?`
            : `Reject all ${pendingEntries.length} pending nomination(s)?`
          }
        </p>
        <p style={{ color: '#94a3b8', fontSize: 11 }}>
          This action will be dispatched for each entry individually.
        </p>
      </Alert>
    </div>
  );
}
