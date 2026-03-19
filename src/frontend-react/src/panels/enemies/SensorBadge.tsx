import { Tag, Intent } from '@blueprintjs/core';

interface SensorBadgeProps {
  sensor_count: number;
}

export function SensorBadge({ sensor_count }: SensorBadgeProps) {
  if (sensor_count === 0) return null;
  const intent = sensor_count >= 3 ? Intent.SUCCESS
               : sensor_count === 2 ? Intent.WARNING
               : Intent.NONE;
  return (
    <Tag intent={intent} minimal style={{ fontSize: 11 }}>
      {sensor_count} SENSOR{sensor_count !== 1 ? 'S' : ''}
    </Tag>
  );
}
