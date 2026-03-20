import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

interface ZoneThreatHeatmapProps {
  scores: [number, number, number][];
}

export function ZoneThreatHeatmap({ scores }: ZoneThreatHeatmapProps) {
  if (!scores || scores.length === 0) return null;

  const { xData, yData } = useMemo(() => {
    let maxX = 0;
    let maxY = 0;
    for (const [x, y] of scores) {
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    const xData = Array.from({ length: maxX + 1 }, (_, i) => String(i));
    const yData = Array.from({ length: maxY + 1 }, (_, i) => String(i));
    return { xData, yData };
  }, [scores]);

  const option = useMemo(() => ({
    animation: false,
    tooltip: {
      position: 'top' as const,
      formatter: (p: { data: [number, number, number] }) =>
        `Zone (${p.data[0]},${p.data[1]}): ${(p.data[2] * 100).toFixed(0)}%`,
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: false,
      orient: 'horizontal' as const,
      left: 'center',
      bottom: 0,
      inRange: { color: ['#1c2127', '#4575b4', '#d73027', '#a50026'] },
      textStyle: { color: '#94a3b8' },
    },
    grid: { top: 10, bottom: 40, left: 10, right: 10, containLabel: false },
    xAxis: { type: 'category' as const, show: false, data: xData },
    yAxis: { type: 'category' as const, show: false, data: yData },
    series: [{
      type: 'heatmap' as const,
      data: scores,
      emphasis: { itemStyle: { shadowBlur: 10 } },
    }],
  }), [scores, xData, yData]);

  return (
    <ReactECharts
      option={option}
      style={{ height: 160, width: '100%' }}
      opts={{ renderer: 'canvas' }}
      notMerge
    />
  );
}
