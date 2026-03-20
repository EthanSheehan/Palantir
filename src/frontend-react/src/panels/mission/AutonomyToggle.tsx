import React from 'react';
import { SegmentedControl } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';
import { useSendMessage } from '../../App';

const OPTIONS = [
  { label: 'MANUAL', value: 'MANUAL' },
  { label: 'SUPERVISED', value: 'SUPERVISED' },
  { label: 'AUTONOMOUS', value: 'AUTONOMOUS' },
];

type AutonomyLevel = 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS';

export function AutonomyToggle() {
  const autonomyLevel = useSimStore(s => s.autonomyLevel);
  const setAutonomyLevel = useSimStore(s => s.setAutonomyLevel);
  const sendMessage = useSendMessage();

  const handleChange = (val: string) => {
    const level = val as AutonomyLevel;
    sendMessage({ action: 'set_autonomy_level', level });
    setAutonomyLevel(level);
  };

  return (
    <div>
      <div style={{
        fontSize: 12,
        fontWeight: 600,
        textTransform: 'uppercase',
        color: '#abb3bf',
        letterSpacing: '0.06em',
        marginBottom: 6,
      }}>
        AUTONOMY LEVEL
      </div>
      <SegmentedControl
        options={OPTIONS}
        value={autonomyLevel}
        onValueChange={handleChange}
        intent="primary"
        small
        fill
      />
    </div>
  );
}
