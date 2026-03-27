import React from 'react';
import { UAV } from '../../store/types';
import { useSimStore } from '../../store/SimulationStore';
import { useSendMessage } from '../../App';
import { MODE_STYLES } from '../../shared/constants';

interface ModeConfig {
  label: string;
  action: string;
  color: string;
  needsTarget: boolean;
}

const MODES: ModeConfig[] = [
  { label: 'SEARCH', action: 'scan_area', color: '#22c55e', needsTarget: false },
  { label: 'FOLLOW', action: 'follow_target', color: '#a78bfa', needsTarget: true },
  { label: 'PAINT', action: 'paint_target', color: '#ef4444', needsTarget: true },
  { label: 'INTERCEPT', action: 'intercept_target', color: '#ff6400', needsTarget: true },
  { label: 'VERIFY', action: 'verify_target', color: MODE_STYLES.VERIFY.color, needsTarget: true },
];

const ACTION_FOR_MODE: Record<string, string> = {
  SEARCH: 'scan_area',
  FOLLOW: 'follow_target',
  PAINT: 'paint_target',
  INTERCEPT: 'intercept_target',
  VERIFY: 'verify_target',
};

interface DroneModeButtonsProps {
  uav: UAV;
}

export function DroneModeButtons({ uav }: DroneModeButtonsProps) {
  const selectedTargetId = useSimStore(s => s.selectedTargetId);
  const sendMessage = useSendMessage();
  const [pulsingAction, setPulsingAction] = React.useState<string | null>(null);

  const handleModeClick = (mode: ModeConfig) => {
    if (mode.needsTarget && !selectedTargetId) {
      setPulsingAction(mode.action);
      setTimeout(() => setPulsingAction(null), 600);
      return;
    }

    const msg: Record<string, unknown> = { action: mode.action, drone_id: uav.id };
    if (mode.needsTarget && selectedTargetId !== null) {
      msg.target_id = selectedTargetId;
    }
    sendMessage(msg);
  };

  const activeAction = ACTION_FOR_MODE[uav.mode];

  return (
    <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
      {MODES.map(mode => {
        const isActive = activeAction === mode.action;
        const isPulsing = pulsingAction === mode.action;
        const needsPickTarget = mode.needsTarget && !selectedTargetId;

        return (
          <button
            key={mode.action}
            onClick={() => handleModeClick(mode)}
            style={{
              flex: 1,
              padding: '3px 0',
              border: `1px solid ${mode.color}`,
              borderRadius: 3,
              background: isActive ? `${mode.color}40` : 'transparent',
              color: mode.color,
              fontSize: '0.6rem',
              fontWeight: 700,
              letterSpacing: '0.04em',
              cursor: 'pointer',
              animation: isPulsing ? 'pulse 0.5s' : undefined,
            }}
          >
            {needsPickTarget && isPulsing ? 'Pick target' : mode.label}
          </button>
        );
      })}
    </div>
  );
}
