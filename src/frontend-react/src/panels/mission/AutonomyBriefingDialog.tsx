import React, { useState } from 'react';
import { Dialog, Button, Intent, Checkbox, Tag, Callout } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';

interface AutonomyBriefingDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const AUTONOMOUS_ACTIONS = [
  'Auto-approve HITL nominations based on confidence thresholds',
  'Auto-authorize Courses of Action (COAs) above priority score 7',
  'Initiate engagement sequences without operator confirmation',
  'Retask drones to high-priority targets automatically',
  'Execute swarm coordination without manual approval',
];

const APPROVAL_REQUIRED_ACTIONS = [
  'Nuclear or chemical weapon employment (disabled)',
  'Engagement outside defined theater bounds',
  'Civilian infrastructure proximity (<500m)',
  'ROE exception requests',
];

export function AutonomyBriefingDialog({ isOpen, onConfirm, onCancel }: AutonomyBriefingDialogProps) {
  const [understood, setUnderstood] = useState(false);
  const autonomyLevel = useSimStore(s => s.autonomyLevel);

  const handleConfirm = () => {
    if (!understood) return;
    setUnderstood(false);
    onConfirm();
  };

  const handleCancel = () => {
    setUnderstood(false);
    onCancel();
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={handleCancel}
      title="AUTONOMOUS MODE BRIEFING"
      className="bp5-dark"
      style={{ width: 460 }}
      icon="warning-sign"
    >
      <div style={{ padding: '16px 20px 0' }}>
        <Callout
          intent={Intent.WARNING}
          icon="warning-sign"
          style={{ marginBottom: 16, fontSize: 12 }}
        >
          Switching to AUTONOMOUS mode will enable AI-driven engagement without per-action
          operator confirmation. Review the following briefing before proceeding.
        </Callout>

        {/* Current → Target */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Tag minimal style={{ background: 'rgba(255,255,255,0.06)', color: '#94a3b8', fontSize: 11 }}>
            {autonomyLevel}
          </Tag>
          <span style={{ color: '#475569', fontSize: 11 }}>→</span>
          <Tag minimal intent={Intent.DANGER} style={{ fontSize: 11, fontWeight: 700 }}>
            AUTONOMOUS
          </Tag>
        </div>

        {/* Autonomous actions */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            fontSize: 10,
            fontWeight: 700,
            color: '#ef4444',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            marginBottom: 6,
          }}>
            Actions AI will perform without approval
          </div>
          {AUTONOMOUS_ACTIONS.map((action, i) => (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 7,
              marginBottom: 4,
              fontSize: 11,
              color: '#cbd5e1',
            }}>
              <span style={{ color: '#ef4444', fontWeight: 700, flexShrink: 0, marginTop: 1 }}>•</span>
              <span>{action}</span>
            </div>
          ))}
        </div>

        {/* Still requires approval */}
        <div style={{ marginBottom: 16 }}>
          <div style={{
            fontSize: 10,
            fontWeight: 700,
            color: '#22c55e',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            marginBottom: 6,
          }}>
            Actions that still require operator approval
          </div>
          {APPROVAL_REQUIRED_ACTIONS.map((action, i) => (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 7,
              marginBottom: 4,
              fontSize: 11,
              color: '#94a3b8',
            }}>
              <span style={{ color: '#22c55e', fontWeight: 700, flexShrink: 0, marginTop: 1 }}>✓</span>
              <span>{action}</span>
            </div>
          ))}
        </div>

        {/* Active ROE */}
        <div style={{
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 4,
          padding: '8px 12px',
          marginBottom: 16,
        }}>
          <div style={{
            fontSize: 10,
            fontWeight: 700,
            color: '#64748b',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            marginBottom: 4,
          }}>
            Active ROE
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>
            Rules of Engagement: WEAPONS FREE (verified targets only)
          </div>
          <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
            Min confidence threshold: 75% • Exclusion zones active
          </div>
        </div>

        <Checkbox
          checked={understood}
          onChange={e => setUnderstood((e.target as HTMLInputElement).checked)}
          label="I understand the system will operate autonomously within the defined ROE"
          style={{ fontSize: 12, color: '#cbd5e1', marginBottom: 16 }}
          className="bp5-dark"
        />
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'flex-end',
        gap: 8,
        padding: '12px 20px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
      }}>
        <Button
          text="Cancel"
          onClick={handleCancel}
          minimal
          style={{ color: '#94a3b8' }}
        />
        <Button
          intent={Intent.DANGER}
          text="Activate Autonomous Mode"
          onClick={handleConfirm}
          disabled={!understood}
          icon="warning-sign"
        />
      </div>
    </Dialog>
  );
}
