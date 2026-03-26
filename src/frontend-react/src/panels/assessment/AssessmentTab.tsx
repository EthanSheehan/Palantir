import React from 'react';
import { useSimStore } from '../../store/SimulationStore';
import { ThreatClusterCard } from './ThreatClusterCard';
import { CoverageGapAlert } from './CoverageGapAlert';
import { ZoneThreatHeatmap } from './ZoneThreatHeatmap';
import { EngagementHistory } from './EngagementHistory';

const SECTION_HEADING: React.CSSProperties = {
  fontSize: '0.7rem',
  fontWeight: 600,
  letterSpacing: '0.08em',
  color: '#94a3b8',
  textTransform: 'uppercase',
  marginBottom: 8,
};

export function AssessmentTab() {
  const assessment = useSimStore(s => s.assessment);

  if (!assessment) {
    return (
      <div style={{ padding: 16, color: '#64748b', fontSize: '0.8rem', fontStyle: 'italic' }}>
        Awaiting assessment data...
      </div>
    );
  }

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Threat Clusters */}
      <div>
        <div style={SECTION_HEADING}>Threat Clusters</div>
        {assessment.clusters.length === 0 ? (
          <div style={{ color: '#64748b', fontSize: '0.7rem', fontStyle: 'italic' }}>
            No threat clusters detected.
          </div>
        ) : (
          assessment.clusters.map(cluster => (
            <ThreatClusterCard key={cluster.cluster_id} cluster={cluster} />
          ))
        )}
      </div>

      {/* Coverage Gaps */}
      <div>
        <div style={SECTION_HEADING}>Coverage Gaps</div>
        <CoverageGapAlert gaps={assessment.coverage_gaps} />
      </div>

      {/* Zone Threat Map */}
      <div>
        <div style={SECTION_HEADING}>Zone Threat Map</div>
        <ZoneThreatHeatmap scores={assessment.zone_threat_scores} />
      </div>

      {/* Movement Corridors */}
      <div>
        <div style={SECTION_HEADING}>Movement Corridors</div>
        <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>
          {assessment.movement_corridors.length} active corridor(s) tracked.
        </div>
        <div style={{ color: '#64748b', fontSize: '0.65rem', marginTop: 4 }}>
          Corridors are visualized on the Cesium globe.
        </div>
      </div>

      {/* Engagement History */}
      <div>
        <div style={SECTION_HEADING}>Engagement History</div>
        <EngagementHistory />
      </div>

    </div>
  );
}
