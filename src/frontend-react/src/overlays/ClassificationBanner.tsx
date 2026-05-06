import React from 'react';

/**
 * Classification banner — top-of-screen chrome found on every defence-grade
 * C2 interface. Reads "UNCLASSIFIED // FOUO // DEMO" by default. Defence
 * software is recognisable as such partly *because* of this banner.
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
  level?: ClassificationLevel;
  caveats?: string[];          // e.g. ["FOUO", "REL TO USA, FVEY"]
  position?: 'top' | 'bottom';
}

export function ClassificationBanner({
  level = 'UNCLASSIFIED',
  caveats = ['FOUO', 'DEMO'],
  position = 'top',
}: Props) {
  const { bg, fg } = LEVEL_COLORS[level];
  const text = [level, ...caveats].join(' // ');
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
