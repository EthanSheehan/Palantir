import React from 'react';
import { Target } from '../../store/types';
import { useSimStore } from '../../store/SimulationStore';
import { TARGET_MAP, STATE_COLORS } from '../../shared/constants';
import { FusionBar } from './FusionBar';
import { SensorBadge } from './SensorBadge';

interface EnemyCardProps {
  target: Target;
  trackers: Array<{ id: number; mode: string }>;
}

const TRACKER_COLORS: Record<string, { color: string; border: string }> = {
  PAINT:     { color: '#ef4444', border: 'rgba(239, 68, 68, 0.4)' },
  INTERCEPT: { color: '#ff6400', border: 'rgba(255, 100, 0, 0.4)' },
  FOLLOW:    { color: '#a78bfa', border: 'rgba(167, 139, 250, 0.4)' },
};

/** Dampen re-renders: only update when semantically meaningful fields change */
function trackersEqual(a: EnemyCardProps['trackers'], b: EnemyCardProps['trackers']): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i].id !== b[i].id || a[i].mode !== b[i].mode) return false;
  }
  return true;
}

function targetsShallowEqual(a: Target, b: Target): boolean {
  return (
    a.id === b.id &&
    a.type === b.type &&
    a.state === b.state &&
    a.detected === b.detected &&
    a.concealed === b.concealed &&
    a.sensor_count === b.sensor_count &&
    Math.round((a.lat ?? 0) * 1000) === Math.round((b.lat ?? 0) * 1000) &&
    Math.round((a.lon ?? 0) * 1000) === Math.round((b.lon ?? 0) * 1000) &&
    Math.round((a.detection_confidence ?? 0) * 100) === Math.round((b.detection_confidence ?? 0) * 100) &&
    Math.round((a.fused_confidence ?? 0) * 100) === Math.round((b.fused_confidence ?? 0) * 100) &&
    (a.sensor_contributions ?? []).length === (b.sensor_contributions ?? []).length
  );
}

const EnemyCardInner = function EnemyCardInner({ target, trackers }: EnemyCardProps) {
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
              TGT
            </span>
            <span style={{ color: config.color, fontWeight: 600, fontSize: '0.8rem' }}>
              TARGET-{target.id}
            </span>
            <SensorBadge sensor_count={target.sensor_count ?? 0} />
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

          {/* Fusion bar + contributing UAV list */}
          {(target.sensor_count ?? 0) > 0 && (
            <div style={{ marginTop: 6, marginBottom: 2 }}>
              <FusionBar
                contributions={target.sensor_contributions ?? []}
                fused_confidence={target.fused_confidence ?? 0}
              />
              {(target.sensor_contributions ?? []).length > 0 && (
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 3 }}>
                  Contributing:{' '}
                  {target.sensor_contributions.slice(0, 5).map((c, i) => (
                    <span key={`${c.uav_id}-${c.sensor_type}`}>
                      {i > 0 && ', '}
                      UAV-{c.uav_id} (<span style={{ color: c.sensor_type === 'EO_IR' ? '#4A90E2' : c.sensor_type === 'SAR' ? '#7ED321' : '#F5A623' }}>{c.sensor_type}</span>)
                    </span>
                  ))}
                  {target.sensor_contributions.length > 5 && ` ...+${target.sensor_contributions.length - 5} more`}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Meta */}
        <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 8 }}>
          <div style={{ color: '#475569', fontSize: '0.65rem' }}>
            {target.lat.toFixed(3)}, {target.lon.toFixed(3)}
          </div>
          <div style={{ color: '#64748b', fontSize: '0.65rem', marginTop: 2 }}>
            {confidence}% CONF
          </div>
        </div>
      </div>
    </div>
  );
};

export const EnemyCard = React.memo(EnemyCardInner, (prev, next) => {
  return targetsShallowEqual(prev.target, next.target) && trackersEqual(prev.trackers, next.trackers);
});
