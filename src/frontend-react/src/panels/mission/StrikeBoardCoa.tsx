import React from 'react';
import { Button, Intent } from '@blueprintjs/core';
import { COA } from '../../store/types';
import { useSendMessage } from '../../App';

export function StrikeBoardCoa({ entryId, coa }: { entryId: string; coa: COA }) {
  const sendMessage = useSendMessage();
  const isAuthorized = coa.status === 'AUTHORIZED';
  const isRejected = coa.status === 'REJECTED';
  const showActions = !isAuthorized && !isRejected;

  const bgColor = isAuthorized
    ? 'rgba(34, 197, 94, 0.1)'
    : isRejected
      ? 'rgba(239, 68, 68, 0.1)'
      : 'rgba(255,255,255,0.02)';

  return (
    <div style={{ background: bgColor, borderRadius: 4, padding: '6px 10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
        <span style={{ fontWeight: 600 }}>
          {coa.effector_name} ({coa.effector_type})
        </span>
        <span style={{ color: '#22c55e' }}>Pk {Math.round(coa.pk_estimate * 100)}%</span>
      </div>

      <div style={{ fontSize: 11, color: '#94a3b8', display: 'flex', gap: 12, marginBottom: 6 }}>
        <span>TTE: {coa.time_to_effect_min.toFixed(1)}min</span>
        <span>Risk: {coa.risk_score}</span>
        <span>Score: {coa.composite_score.toFixed(1)}</span>
      </div>

      {showActions && (
        <div style={{ display: 'flex', gap: 6 }}>
          <Button
            intent={Intent.SUCCESS}
            small
            minimal
            text="AUTHORIZE"
            onClick={() => sendMessage({ action: 'authorize_coa', entry_id: entryId, coa_id: coa.id, rationale: 'COA authorized' })}
          />
          <Button
            intent={Intent.DANGER}
            small
            minimal
            text="REJECT"
            onClick={() => sendMessage({ action: 'reject_coa', entry_id: entryId, rationale: 'COA rejected' })}
          />
        </div>
      )}
    </div>
  );
}
