import React from 'react';
import { Button, Intent } from '@blueprintjs/core';
import type { Target, SwarmTask } from '../../store/types';

const SENSOR_TYPES = ['EO_IR', 'SAR', 'SIGINT'] as const;

const SENSOR_COLORS: Record<string, string> = {
  EO_IR: '#4A90E2',
  SAR: '#7ED321',
  SIGINT: '#F5A623',
};

const SENSOR_LABELS: Record<string, string> = {
  EO_IR: 'EO/IR',
  SAR: 'SAR',
  SIGINT: 'SIGINT',
};

interface SwarmPanelProps {
  target: Target;
  swarmTask: SwarmTask | undefined;
}

function SwarmPanelInner({ target, swarmTask }: SwarmPanelProps) {
  const coveredSensors = new Set(
    target.sensor_contributions.map(c => c.sensor_type)
  );
  const hasSwarm = swarmTask && swarmTask.assigned_uav_ids.length > 0;

  const handleRequest = () => {
    window.dispatchEvent(new CustomEvent('palantir:send', {
      detail: { action: 'request_swarm', target_id: target.id }
    }));
  };

  const handleRelease = () => {
    window.dispatchEvent(new CustomEvent('palantir:send', {
      detail: { action: 'release_swarm', target_id: target.id }
    }));
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
      <span style={{ fontSize: 10, color: '#8abbff', marginRight: 2 }}>SWARM</span>
      {SENSOR_TYPES.map(sensor => {
        const covered = coveredSensors.has(sensor);
        return (
          <div
            key={sensor}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              padding: '1px 4px',
              borderRadius: 3,
              background: covered ? `${SENSOR_COLORS[sensor]}22` : 'transparent',
              border: `1px solid ${covered ? SENSOR_COLORS[sensor] : '#394b59'}`,
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: covered ? SENSOR_COLORS[sensor] : 'transparent',
                border: `1px solid ${SENSOR_COLORS[sensor]}`,
              }}
            />
            <span style={{
              fontSize: 9,
              color: covered ? SENSOR_COLORS[sensor] : '#5c7080',
              fontWeight: covered ? 600 : 400,
            }}>
              {SENSOR_LABELS[sensor]}
            </span>
          </div>
        );
      })}
      <div style={{ marginLeft: 'auto' }}>
        {hasSwarm ? (
          <Button
            small
            minimal
            intent={Intent.WARNING}
            onClick={handleRelease}
            style={{ fontSize: 9, padding: '0 4px', minHeight: 18 }}
          >
            RELEASE
          </Button>
        ) : (
          <Button
            small
            minimal
            intent={Intent.PRIMARY}
            onClick={handleRequest}
            style={{ fontSize: 9, padding: '0 4px', minHeight: 18 }}
          >
            REQUEST
          </Button>
        )}
      </div>
    </div>
  );
}

function swarmPanelEqual(prev: SwarmPanelProps, next: SwarmPanelProps): boolean {
  const prevCov = prev.target.sensor_contributions.map(c => c.sensor_type).sort().join(',');
  const nextCov = next.target.sensor_contributions.map(c => c.sensor_type).sort().join(',');
  if (prevCov !== nextCov) return false;
  const prevIds = prev.swarmTask?.assigned_uav_ids?.length ?? 0;
  const nextIds = next.swarmTask?.assigned_uav_ids?.length ?? 0;
  return prevIds === nextIds;
}

export const SwarmPanel = React.memo(SwarmPanelInner, swarmPanelEqual);
