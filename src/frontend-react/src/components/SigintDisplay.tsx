import React, { useRef, useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { useSimStore } from '../store/SimulationStore';

const FREQ_BINS = 64;
const TIME_SLOTS = 60;

interface SigintDisplayProps {
  droneId: number | null;
  width: number;
  height: number;
}

function makeEmptyBuffer(): number[][] {
  return Array.from({ length: TIME_SLOTS }, () => Array(FREQ_BINS).fill(0));
}

export function SigintDisplay({ droneId, width, height }: SigintDisplayProps) {
  const bufferRef = useRef<number[][]>(makeEmptyBuffer());
  const [tickCount, setTickCount] = useState(0);

  useEffect(() => {
    if (droneId === null) return;

    const interval = setInterval(() => {
      const { uavs, targets } = useSimStore.getState();
      const drone = uavs.find(u => u.id === droneId);

      const newColumn = Array(FREQ_BINS).fill(0).map(() => Math.random() * 0.08);

      if (drone) {
        for (const target of targets) {
          if (target.state === 'UNDETECTED') continue;
          for (const contrib of target.sensor_contributions) {
            if (contrib.sensor_type === 'SIGINT' && contrib.uav_id === droneId) {
              const freqBin = (target.id * 7) % FREQ_BINS;
              newColumn[freqBin] = Math.max(newColumn[freqBin], contrib.confidence);
            }
          }
        }
      }

      const buf = bufferRef.current;
      buf.shift();
      buf.push(newColumn);

      setTickCount(n => n + 1);
    }, 500);

    return () => clearInterval(interval);
  }, [droneId]);

  const option = useMemo(() => {
    const buf = bufferRef.current;
    const flatData: [number, number, number][] = [];
    for (let t = 0; t < TIME_SLOTS; t++) {
      for (let f = 0; f < FREQ_BINS; f++) {
        flatData.push([t, f, buf[t][f]]);
      }
    }
    return {
      animation: false,
      xAxis: {
        type: 'category' as const,
        data: Array.from({ length: TIME_SLOTS }, (_, i) => String(i)),
        show: false,
      },
      yAxis: {
        type: 'category' as const,
        data: Array.from({ length: FREQ_BINS }, (_, i) => String(i)),
        show: false,
      },
      visualMap: {
        min: 0,
        max: 1,
        inRange: { color: ['#000814', '#001d3d', '#003566', '#ffd60a', '#ffffff'] },
        show: false,
      },
      series: [{
        type: 'heatmap' as const,
        data: flatData,
        emphasis: { disabled: true },
      }],
      grid: { top: 0, bottom: 0, left: 0, right: 0 },
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickCount]);

  if (droneId === null) {
    return (
      <div
        style={{
          width,
          height,
          background: '#000814',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#003566',
          fontFamily: 'monospace',
          fontSize: 12,
        }}
      >
        NO SIGINT FEED
      </div>
    );
  }

  return (
    <ReactECharts
      option={option}
      style={{ width, height }}
      opts={{ renderer: 'canvas' }}
      notMerge={false}
      theme="palantir"
    />
  );
}
