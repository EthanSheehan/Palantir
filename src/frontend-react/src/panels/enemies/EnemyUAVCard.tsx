import { Tag } from '@blueprintjs/core';
import { EnemyUAV } from '../../store/types';
import { ENEMY_MODE_STYLES } from '../../shared/constants';

interface Props {
  enemyUav: EnemyUAV;
}

export function EnemyUAVCard({ enemyUav }: Props) {
  const modeStyle = ENEMY_MODE_STYLES[enemyUav.mode] || ENEMY_MODE_STYLES['RECON'];
  const confidencePct = Math.round(enemyUav.fused_confidence * 100);

  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: `1px solid ${modeStyle.color}40`,
        borderRadius: 4,
        padding: '8px 10px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            background: modeStyle.color,
            color: '#000',
            padding: '1px 5px',
            borderRadius: 3,
            fontSize: '0.6rem',
            fontWeight: 800,
            letterSpacing: '0.03em',
          }}>
            UAV
          </span>
          <span style={{ color: modeStyle.color, fontWeight: 600, fontSize: '0.8rem' }}>
            ENM-{enemyUav.id - 1000}
          </span>
        </div>
        <Tag
          minimal
          style={{ background: `${modeStyle.color}30`, color: modeStyle.color, fontSize: 10 }}
        >
          {modeStyle.label}
        </Tag>
      </div>
      <div style={{ marginTop: 6, display: 'flex', gap: 12, fontSize: 11, color: '#94a3b8', flexWrap: 'wrap' }}>
        <span>Confidence: {confidencePct}%</span>
        <span>Sensors: {enemyUav.sensor_count}</span>
        {enemyUav.is_jamming && (
          <Tag intent="warning" minimal style={{ fontSize: 10 }}>JAMMING</Tag>
        )}
      </div>
    </div>
  );
}
