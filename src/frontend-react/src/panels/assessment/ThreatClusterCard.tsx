import React from 'react';
import { ThreatCluster } from '../../store/types';

const CLUSTER_COLORS: Record<ThreatCluster['cluster_type'], string> = {
  SAM_BATTERY: '#ef4444',
  AD_NETWORK:  '#f59e0b',
  CONVOY:      '#3b82f6',
  CP_COMPLEX:  '#a78bfa',
  MIXED:       '#94a3b8',
};

interface ThreatClusterCardProps {
  cluster: ThreatCluster;
}

export function ThreatClusterCard({ cluster }: ThreatClusterCardProps) {
  const color = CLUSTER_COLORS[cluster.cluster_type] ?? '#94a3b8';
  const maxShown = 5;
  const shown = cluster.member_target_ids.slice(0, maxShown);
  const overflow = cluster.member_target_ids.length - maxShown;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)',
      border: `1px solid ${color}44`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 4,
      padding: '8px 10px',
      marginBottom: 6,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{
          background: color,
          color: '#000',
          padding: '1px 6px',
          borderRadius: 3,
          fontSize: '0.6rem',
          fontWeight: 800,
          letterSpacing: '0.03em',
        }}>
          {cluster.cluster_type}
        </span>
        <span style={{ color: '#64748b', fontSize: '0.65rem' }}>
          {cluster.cluster_id}
        </span>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 4 }}>
        <span style={{ color: '#94a3b8', fontSize: '0.7rem' }}>
          {cluster.member_target_ids.length} targets
        </span>
        <span style={{ color: color, fontSize: '0.7rem', fontWeight: 600 }}>
          Threat: {(cluster.threat_score * 100).toFixed(0)}%
        </span>
      </div>

      {/* Member list */}
      <div style={{ color: '#64748b', fontSize: '0.65rem' }}>
        {shown.map(id => `TGT-${id}`).join(', ')}
        {overflow > 0 && ` +${overflow} more`}
      </div>
    </div>
  );
}
