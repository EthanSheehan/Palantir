import React from 'react';
import { SegmentedControl } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';
import { useSendMessage } from '../../App';

const COVERAGE_OPTIONS = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Threat-Adaptive', value: 'threat_adaptive' },
];

export function CoverageModeToggle() {
  const coverageMode = useSimStore(s => s.coverageMode);
  const sendMessage = useSendMessage();

  return (
    <div style={{ padding: '8px 16px' }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4, letterSpacing: '0.05em' }}>COVERAGE MODE</div>
      <SegmentedControl
        options={COVERAGE_OPTIONS}
        value={coverageMode}
        onValueChange={(val) => sendMessage({ action: 'set_coverage_mode', mode: val })}
        small
      />
    </div>
  );
}
