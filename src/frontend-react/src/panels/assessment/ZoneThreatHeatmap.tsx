import { useMemo } from 'react';

interface ZoneThreatHeatmapProps {
  scores: [number, number, number][];
}

function threatColor(value: number): string {
  if (value >= 0.8) return '#dc2626';
  if (value >= 0.5) return '#f59e0b';
  if (value >= 0.2) return '#3b82f6';
  return '#334155';
}

function threatLabel(value: number): string {
  if (value >= 0.8) return 'CRITICAL';
  if (value >= 0.5) return 'HIGH';
  if (value >= 0.2) return 'MODERATE';
  return 'LOW';
}

export function ZoneThreatHeatmap({ scores }: ZoneThreatHeatmapProps) {
  const sorted = useMemo(() => {
    if (!scores || scores.length === 0) return [];
    return [...scores]
      .sort((a, b) => b[2] - a[2])
      .slice(0, 12);
  }, [scores]);

  if (sorted.length === 0) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.7rem', fontStyle: 'italic' }}>
        No zone threats detected.
      </div>
    );
  }

  const maxVal = sorted[0]?.[2] || 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {sorted.map(([x, y, val]) => (
        <div
          key={`${x}-${y}`}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <span style={{
            fontSize: '0.6rem',
            color: '#64748b',
            fontFamily: 'monospace',
            width: 36,
            flexShrink: 0,
          }}>
            ({x},{y})
          </span>
          <div style={{
            flex: 1,
            height: 10,
            background: '#1e293b',
            borderRadius: 2,
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${(val / Math.max(maxVal, 0.01)) * 100}%`,
              height: '100%',
              background: threatColor(val),
              borderRadius: 2,
              transition: 'width 0.3s ease',
            }} />
          </div>
          <span style={{
            fontSize: '0.55rem',
            fontWeight: 600,
            color: threatColor(val),
            width: 52,
            textAlign: 'right',
            flexShrink: 0,
          }}>
            {threatLabel(val)}
          </span>
        </div>
      ))}
      {scores.length > 12 && (
        <div style={{ color: '#475569', fontSize: '0.6rem', textAlign: 'center', marginTop: 2 }}>
          +{scores.length - 12} more zones
        </div>
      )}
    </div>
  );
}
