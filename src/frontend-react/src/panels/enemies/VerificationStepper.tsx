import React from 'react';
import { ProgressBar, Intent, Button } from '@blueprintjs/core';

const STEPS = ['DETECTED', 'CLASSIFIED', 'VERIFIED', 'NOMINATED'] as const;

function dotColor(stepIdx: number, currentIdx: number): string {
  if (currentIdx === -1) return '#5C7080';
  if (stepIdx < currentIdx) return '#0F9960';
  if (stepIdx === currentIdx) return '#D9822B';
  return '#5C7080';
}

interface VerificationStepperProps {
  state: string;
  fused_confidence: number;
  next_threshold: number | null;
  time_in_state_sec: number;
  onManualVerify?: () => void;
}

export function VerificationStepper({
  state,
  fused_confidence,
  next_threshold,
  onManualVerify,
}: VerificationStepperProps) {
  const currentIdx = STEPS.indexOf(state as typeof STEPS[number]);

  const progressValue =
    next_threshold !== null && next_threshold > 0
      ? Math.min(1.0, fused_confidence / next_threshold)
      : 1.0;

  const progressIntent =
    state === 'CLASSIFIED' ? Intent.WARNING : Intent.PRIMARY;

  return (
    <div style={{ padding: '4px 0' }}>
      {/* Step dots */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
        {STEPS.map((step, idx) => (
          <React.Fragment key={step}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: dotColor(idx, currentIdx),
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 10,
                  color: '#A7B6C2',
                  marginTop: 2,
                  whiteSpace: 'nowrap',
                }}
              >
                {step.slice(0, 4)}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div
                style={{
                  width: 12,
                  height: 1,
                  backgroundColor: '#394B59',
                  marginBottom: 14,
                  flexShrink: 0,
                }}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Progress bar */}
      {next_threshold !== null && (
        <ProgressBar
          value={progressValue}
          intent={progressIntent}
          animate={false}
          stripes={false}
          style={{ height: 4 }}
        />
      )}

      {/* Manual VERIFY button — only for CLASSIFIED targets */}
      {state === 'CLASSIFIED' && onManualVerify !== undefined && (
        <Button
          small
          intent={Intent.WARNING}
          text="VERIFY"
          onClick={onManualVerify}
          style={{ marginTop: 4 }}
        />
      )}
    </div>
  );
}
