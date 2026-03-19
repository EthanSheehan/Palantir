import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { SensorContributionPayload } from '../../store/types';

const SENSOR_COLORS: Record<string, string> = {
  EO_IR: '#4A90E2',
  SAR: '#7ED321',
  SIGINT: '#F5A623',
};

const SENSORS = ['EO_IR', 'SAR', 'SIGINT'] as const;

interface FusionBarProps {
  contributions: SensorContributionPayload[];
  fused_confidence: number;
}

export function FusionBar({ contributions, fused_confidence }: FusionBarProps) {
  if (!contributions || contributions.length === 0) return null;

  const option = useMemo(() => {
    const perType: Record<string, number> = {};
    for (const c of contributions) {
      if (!perType[c.sensor_type] || c.confidence > perType[c.sensor_type]) {
        perType[c.sensor_type] = c.confidence;
      }
    }
    return {
      tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
      xAxis: { type: 'value' as const, max: 1.0, show: false },
      yAxis: { type: 'category' as const, data: ['FUSION'], show: false },
      grid: { top: 0, bottom: 0, left: 0, right: 0, containLabel: false },
      series: SENSORS.map(stype => ({
        name: stype,
        type: 'bar' as const,
        stack: 'fusion',
        barMaxWidth: 12,
        itemStyle: { color: SENSOR_COLORS[stype] },
        data: [perType[stype] ?? 0],
      })),
    };
  }, [contributions, fused_confidence]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <ReactECharts option={option} style={{ height: 12, width: 120, flex: '0 0 120px' }} opts={{ renderer: 'canvas' }} />
      <span style={{ color: '#aaa', fontSize: 11 }}>
        {(fused_confidence * 100).toFixed(0)}%
      </span>
    </div>
  );
}
