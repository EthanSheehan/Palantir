import React from 'react';
import { useSimStore } from '../store/SimulationStore';

/**
 * Classification banner — top-of-screen chrome found on every defence-grade
 * C2 interface. Reads "UNCLASSIFIED // FOUO // DEMO" by default. Reactive
 * to the live `persona` field in the store so the banner updates the
 * moment the operator flips persona via the VerticalTaskbar.
 *
 * Maven runs a single classification per deployment; we render all three at
 * once and let the operator demonstrate cross-domain dynamic security
 * filtering.
 */
export type ClassificationLevel =
  | 'UNCLASSIFIED'
  | 'CUI'
  | 'CONFIDENTIAL'
  | 'SECRET'
  | 'TOP SECRET';

const LEVEL_COLORS: Record<ClassificationLevel, { bg: string; fg: string }> = {
  UNCLASSIFIED:  { bg: '#0a7c2f', fg: '#ffffff' },  // green
  CUI:           { bg: '#5d3d8a', fg: '#ffffff' },  // purple
  CONFIDENTIAL:  { bg: '#1d4ed8', fg: '#ffffff' },  // blue
  SECRET:        { bg: '#b91c1c', fg: '#ffffff' },  // red
  'TOP SECRET':  { bg: '#fbbf24', fg: '#0b0f17' },  // amber-on-black
};

interface Props {
  level?: ClassificationLevel;        // override; default reads from store persona
  caveats?: string[];                 // e.g. ["FOUO", "REL TO USA, FVEY"]
  position?: 'top' | 'bottom';
}

export function ClassificationBanner({
  level: levelProp,
  caveats = ['FOUO', 'DEMO'],
  position = 'top',
}: Props) {
  const persona = useSimStore(s => s.persona);
  // Map persona → banner level. Persona "SECRET" is rendered as SECRET; CUI
  // as CUI; UNCLASSIFIED stays UNCLASSIFIED.
  const level = (levelProp ?? persona) as ClassificationLevel;
  const { bg, fg } = LEVEL_COLORS[level] ?? LEVEL_COLORS.UNCLASSIFIED;
  // CUI / SECRET strip the FOUO caveat (it's UNCLASS-only) and replace with
  // a tier-appropriate one.
  let effectiveCaveats = caveats;
  if (level === 'SECRET') effectiveCaveats = ['NOFORN', 'DEMO'];
  else if (level === 'CUI') effectiveCaveats = ['FOUO', 'DEMO'];
  const text = [level, ...effectiveCaveats].join(' // ');
  return (
    <div
      role="alert"
      aria-label={`Classification banner: ${text}`}
      style={{
        background: bg,
        color: fg,
        textAlign: 'center',
        fontFamily: 'monospace',
        fontWeight: 700,
        fontSize: 11,
        letterSpacing: '0.18em',
        padding: '3px 0',
        borderTop: position === 'bottom' ? `2px solid ${fg}22` : undefined,
        borderBottom: position === 'top' ? `2px solid ${fg}22` : undefined,
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      {text}
    </div>
  );
}
