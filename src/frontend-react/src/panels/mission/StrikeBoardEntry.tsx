import React from 'react';
import { Button, Intent, Tag } from '@blueprintjs/core';
import { StrikeEntry, COA } from '../../store/types';
import { useSimStore } from '../../store/SimulationStore';
import { useSendMessage } from '../../App';
import { StrikeBoardCoa } from './StrikeBoardCoa';

const STATUS_COLORS: Record<string, string> = {
  PENDING: '#eab308', APPROVED: '#22c55e', REJECTED: '#ef4444', RETASKED: '#3b82f6',
};

export function StrikeBoardEntry({ entry }: { entry: StrikeEntry }) {
  const sendMessage = useSendMessage();
  const cachedCoas = useSimStore(s => s.cachedCoas[entry.id]) as COA[] | undefined;
  const statusColor = STATUS_COLORS[entry.status] || '#94a3b8';

  return (
    <div
      style={{
        borderLeft: `3px solid ${statusColor}`,
        background: 'rgba(255,255,255,0.03)',
        borderRadius: 4,
        padding: '8px 12px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{entry.target_type}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#64748b', fontSize: 11 }}>{entry.id}</span>
          <Tag style={{ background: statusColor, color: '#fff' }} minimal>{entry.status}</Tag>
        </div>
      </div>

      <div style={{ fontSize: 11, color: '#94a3b8', display: 'flex', gap: 12, marginBottom: 8 }}>
        <span>Conf: {Math.round(entry.detection_confidence * 100)}%</span>
        <span>Priority: {entry.priority_score}</span>
        <span>ROE: {entry.roe_evaluation}</span>
      </div>

      {entry.status === 'PENDING' && (
        <div style={{ display: 'flex', gap: 6 }}>
          <Button
            intent={Intent.SUCCESS}
            small
            minimal
            text="APPROVE"
            onClick={() => sendMessage({ action: 'approve_nomination', entry_id: entry.id, rationale: 'Commander approved' })}
          />
          <Button
            intent={Intent.DANGER}
            small
            minimal
            text="REJECT"
            onClick={() => sendMessage({ action: 'reject_nomination', entry_id: entry.id, rationale: 'Commander rejected' })}
          />
          <Button
            intent={Intent.WARNING}
            small
            minimal
            text="RETASK"
            onClick={() => sendMessage({ action: 'retask_nomination', entry_id: entry.id, rationale: 'Retask requested' })}
          />
        </div>
      )}

      {entry.status === 'APPROVED' && cachedCoas && cachedCoas.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
          {cachedCoas.map(coa => (
            <StrikeBoardCoa key={coa.id} entryId={entry.id} coa={coa} />
          ))}
        </div>
      )}
    </div>
  );
}
