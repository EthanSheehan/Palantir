import React from 'react';
import { Target } from '../../store/types';
import { useSimStore } from '../../store/SimulationStore';
import { TARGET_MAP, STATE_COLORS } from '../../shared/constants';

interface EnemyCardProps {
  target: Target;
  trackers: Array<{ id: number; mode: string }>;
}

const TRACKER_COLORS: Record<string, { color: string; border: string }> = {
  PAINT:     { color: '#ef4444', border: 'rgba(239, 68, 68, 0.4)' },
  INTERCEPT: { color: '#ff6400', border: 'rgba(255, 100, 0, 0.4)' },
  FOLLOW:    { color: '#a78bfa', border: 'rgba(167, 139, 250, 0.4)' },
};

export function EnemyCard({ target, trackers }: EnemyCardProps) {
  const selectedTargetId = useSimStore(s => s.selectedTargetId);
  const selectTarget = useSimStore(s => s.selectTarget);

  const targetState = target.state || (target.detected ? 'DETECTED' : 'UNDETECTED');
  const config = TARGET_MAP[target.type] || { color: '#ffcc00', label: 'TGT' };
  const stateStyle = STATE_COLORS[targetState] || { color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.1)' };
  const confidence = target.detection_confidence !== undefined
    ? Math.round(target.detection_confidence * 100)
    : (target.detected ? 100 : 0);

  const isSelected = target.id === selectedTargetId;
  const isEngaged = targetState === 'ENGAGED';
  const isNeutralized = targetState === 'NEUTRALIZED';

  const cardStyle: React.CSSProperties = {
    background: 'rgba(255,255,255,0.04)',
    border: `1px solid ${isSelected ? stateStyle.color : isEngaged ? '#dc2626' : 'rgba(255,255,255,0.1)'}`,
    borderRadius: 4,
    padding: '8px 10px',
    cursor: 'pointer',
    opacity: isNeutralized ? 0.5 : 1,
    animation: isEngaged ? 'enemyEngagedPulse 1s infinite' : undefined,
  };

  const handleClick = () => {
    selectTarget(target.id);
  };

  return (
    <div style={cardStyle} onClick={handleClick}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          {/* ID row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <span style={{
              background: config.color,
              color: '#000',
              padding: '1px 5px',
              borderRadius: 3,
              fontSize: '0.6rem',
              fontWeight: 800,
              letterSpacing: '0.03em',
            }}>
              {config.label}
            </span>
            <span style={{ color: config.color, fontWeight: 600, fontSize: '0.8rem' }}>
              TARGET-{target.id}
            </span>
            {target.concealed && (
              <span style={{
                color: '#94a3b8',
                border: '1px solid rgba(148, 163, 184, 0.4)',
                borderRadius: 3,
                padding: '0px 4px',
                fontSize: '0.55rem',
                fontWeight: 700,
                letterSpacing: '0.04em',
              }}>
                CONCEALED
              </span>
            )}
          </div>

          {/* Type name */}
          <div style={{ color: '#64748b', fontSize: '0.65rem', marginBottom: 4 }}>
            {target.type}
          </div>

          {/* State badge */}
          <span style={{
            color: stateStyle.color,
            background: stateStyle.bg,
            borderRadius: 3,
            padding: '1px 6px',
            fontSize: '0.65rem',
            fontWeight: 700,
          }}>
            {targetState}
          </span>

          {/* Tracker tags */}
          {trackers.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 4 }}>
              {trackers.map(tr => {
                const tc = TRACKER_COLORS[tr.mode] || TRACKER_COLORS.FOLLOW;
                return (
                  <span
                    key={`${tr.id}-${tr.mode}`}
                    style={{
                      color: tc.color,
                      border: `1px solid ${tc.border}`,
                      borderRadius: 3,
                      padding: '0px 4px',
                      fontSize: '0.6rem',
                      fontWeight: 700,
                    }}
                  >
                    UAV-{tr.id} {tr.mode}
                  </span>
                );
              })}
            </div>
          )}
        </div>

        {/* Meta */}
        <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 8 }}>
          <div style={{ color: '#475569', fontSize: '0.65rem' }}>
            {target.lat.toFixed(4)}, {target.lon.toFixed(4)}
          </div>
          <div style={{ color: '#64748b', fontSize: '0.65rem', marginTop: 2 }}>
            {confidence}% CONF
          </div>
        </div>
      </div>
    </div>
  );
}
